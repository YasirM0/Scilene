"""
Lightweight semantic search via ONNX Runtime (#143 follow-up) -- a
SEPARATE, opt-in search path alongside the deterministic keyword-based
services/recommender.py. Never imported BY that module, and never
touches its scoring/ranking logic -- the two are independent ranking
strategies a route can call, not layers of one pipeline. This module
does import one small, pure utility (parse_usd_amount) FROM
recommender.py to avoid duplicating APC-string parsing; that's a
one-directional, read-only dependency on a stable helper, not a
coupling of the two ranking strategies themselves.

Two models, routed by detected language (#143 multilingual follow-up):
  - "en": bge-small-en-v1.5 -- best quality of 8 candidates benchmarked
    for English, but catastrophically bad on Indonesian (recall@10
    0.299 -> 0.000; it's an English-only model, this isn't a tuning
    issue). See docs/experiments/embedding_benchmarks.md.
  - "multilingual": multilingual-e5-small (quantized ONNX) -- the best
    of 5 multilingual candidates tested (multilingual-e5-base,
    paraphrase-multilingual-MiniLM-L12-v2, LaBSE, and nomic-embed-text-v2-moe,
    which had no ONNX export and so couldn't be shipped at all) for
    Arabic/Indonesian retrieval, without sacrificing deployability.

Both run on plain ONNX Runtime + tokenizers rather than
sentence-transformers + torch: the latter would add ~350-400MB of
dependencies (torch alone is ~192MB even CPU-only) per model, risking
Heroku's 500MB slug limit. Both model files are also int8-quantized
(bge-small 127MB -> 33.8MB, multilingual-e5-small 113MB -> 44.3MB),
which was ALSO necessary to clear GitHub's separate 100MB-per-file
push limit -- the first attempt to push this feature failed outright
(pre-receive hook rejection) with both files still full-size. Verified
numerically near-identical to each fp32 reference (cosine similarity
0.97-0.99 on real test embeddings) before being trusted here.

multilingual-e5-small's vocabulary is ALSO trimmed: 250,037 -> 58,226
tokens (kept = union of tokens seen tokenizing English/Arabic/Indonesian
Wikipedia samples + Scilene's own full journal corpus + the #112
benchmark's 166 real abstracts, so both general and domain vocabulary
are covered). This is what actually made the multilingual model
deployable at all -- its 250K-token vocabulary was consuming ~350MB+
of runtime RAM by itself (dwarfing the transformer body), regardless
of quantization, because embedding-table memory scales with vocab
size, not just parameter count. Verified byte-identical output
(cosine similarity 1.0000, zero <unk> tokens) vs. the untrimmed model
on real English/Arabic/Indonesian test queries before quantizing.
Loading both models together (memory arena disabled -- see
_get_session) now costs ~400MB resident, down from ~870MB
pre-optimization; see #145 for the still-open task of confirming this
against real Heroku dyno memory, not just a local measurement.

Runs entirely locally -- no external API calls at request time,
matching the same "local, indexed database" philosophy the existing
keyword search already advertises. Model files live under models/
(committed directly to the repo, same convention as
data/journal_intelligence.db -- see that file's own git history for
precedent).
"""

import json
import threading
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from services.language_detection import detect_language
from services.recommender import parse_usd_amount
from services.repository import get_journals_by_ids
from utils.publication_types import format_publication_type_badge

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models"

# Each model's asymmetric-retrieval convention (query gets an
# instruction/prefix, documents get their own or none) and pooling
# strategy (CLS-token vs. mean) -- getting either wrong silently
# produces degraded, not erroneous, results, so both are pinned here
# explicitly rather than guessed generically. max_seq_length matches
# each model's own sentence_bert_config.json / model card.
MODEL_CONFIGS = {
    "en": {
        "dir": MODELS_ROOT / "bge-small-en-v1.5-onnx",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "doc_prefix": "",
        "pooling": "cls",
        "max_seq_length": 512,
        "pad_id": 0,
        "pad_token": "[PAD]",
    },
    "multilingual": {
        "dir": MODELS_ROOT / "multilingual-e5-small-onnx",
        "query_prefix": "query: ",
        "doc_prefix": "passage: ",
        "pooling": "mean",
        "max_seq_length": 512,
        # XLM-R/Unigram convention: <s>=0 <pad>=1 </s>=2 <unk>=3 -- NOT
        # bge-small's WordPiece pad_id=0 (which is <s>/BOS here, not
        # pad). Harmless either way in practice since embed()'s mean
        # pooling masks out padded positions by attention_mask before
        # averaging, but using the model's real pad token is still the
        # correct thing to do, not just a no-op detail to skip.
        "pad_id": 1,
        "pad_token": "<pad>",
    },
}

# Percentile-based, same shape as (but NOT imported from)
# services/recommender.py's own _assign_confidence() -- consistent
# visual language for the user (same five tiers, same "top fifth of
# THIS search's own results" relativity) without semantic_search.py
# importing scoring logic from the deterministic engine, or vice
# versa. Cosine similarity and the recommender's keyword-hit score are
# different metrics on different scales; only the RANK-based bucketing
# approach carries over, not any numeric threshold.
_CONFIDENCE_LEVELS = ("Poor", "Weak", "Moderate", "Strong", "Excellent")

# Languages detect_language() (#89, English/Arabic/Indonesian only)
# can identify that bge-small-en-v1.5 handles badly enough to need the
# multilingual fallback. English, and anything detect_language()
# *couldn't* confidently identify, both stay on "en": in the same
# per-language benchmark, bge-small was also the strongest model on
# the "undetected language" bucket (recall@10 0.217 vs.
# multilingual-e5-small's 0.130) -- text langdetect can't confidently
# place is more often mixed-in-mostly-English than genuinely
# Arabic/Indonesian, so defaulting it to the stronger model is the
# safer call, not a gap in the routing.
FALLBACK_LANGUAGES = {"Arabic", "Indonesian"}


def route_model_key(query_text: str) -> str:
    """
    Which model a given piece of text should use. Detects language on
    the text AS A WHOLE -- a search query is already abstract+tags
    concatenated into one string before it gets here (see
    web/routers/search.py's _execute_semantic_search), and embeddings
    from different models can't be mixed within a single query anyway,
    so there's no meaningful way to route "half the query" separately
    even for a genuinely mixed-language abstract+tags combination.
    """
    return "multilingual" if detect_language(query_text) in FALLBACK_LANGUAGES else "en"


_tokenizers = {}
_sessions = {}
_load_lock = threading.Lock()


def _get_tokenizer(model_key):
    if model_key not in _tokenizers:
        with _load_lock:
            if model_key not in _tokenizers:
                config = MODEL_CONFIGS[model_key]
                tokenizer = Tokenizer.from_file(str(config["dir"] / "tokenizer.json"))
                tokenizer.enable_padding(pad_id=config["pad_id"], pad_token=config["pad_token"])
                tokenizer.enable_truncation(max_length=config["max_seq_length"])
                _tokenizers[model_key] = tokenizer
    return _tokenizers[model_key]


def _get_session(model_key):
    # Lazy singleton per model -- loaded on first actual use (not at
    # import time, let alone app startup), so nothing pays either
    # model's cost unless the opt-in semantic search path is actually
    # exercised for a query landing on it. warm_model() below is the
    # one deliberate exception, called ahead of time once we already
    # know a query is headed this way.
    if model_key not in _sessions:
        with _load_lock:
            if model_key not in _sessions:
                config = MODEL_CONFIGS[model_key]
                # Arena/mem-pattern pre-allocation trades RAM for
                # speed; on a 512MB Heroku dyon running BOTH models,
                # RAM is the binding constraint, not latency (measured
                # ~750-870MB -> ~400MB total with these disabled, see
                # this module's docstring). Small single-query batches
                # don't benefit much from arena reuse anyway.
                opts = ort.SessionOptions()
                opts.enable_cpu_mem_arena = False
                opts.enable_mem_pattern = False
                _sessions[model_key] = ort.InferenceSession(
                    str(config["dir"] / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"]
                )
    return _sessions[model_key]


def warm_model(model_key: str) -> None:
    """
    Loads a model's tokenizer + ONNX session into this process's cache
    without running any inference. Meant to be called from a
    background thread (see web/routers/interpreter.py's language
    detection on abstract entry) the moment a non-English language is
    detected, so the multilingual fallback is already resident by the
    time the user reaches Search instead of paying its cold-start cost
    on the first semantic query. Safe to call redundantly -- a no-op
    once the model's already loaded.
    """
    _get_tokenizer(model_key)
    _get_session(model_key)


def embed(texts: list[str], model_key: str = "en") -> np.ndarray:
    """
    L2-normalized embeddings for a batch of strings, shape (N, 384).
    """
    config = MODEL_CONFIGS[model_key]
    tokenizer = _get_tokenizer(model_key)
    session = _get_session(model_key)

    encodings = tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    outputs = session.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    })
    last_hidden = outputs[0]

    if config["pooling"] == "cls":
        pooled = last_hidden[:, 0, :]
    else:
        # Mean pooling, attention-mask-weighted -- padded positions
        # must not count toward the average (see multilingual-e5-small's
        # own model card).
        mask = attention_mask[:, :, None].astype(np.float32)
        summed = (last_hidden * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), 1e-9, None)
        pooled = summed / counts

    norm = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / norm


def embed_query(text: str, model_key: str = "en") -> np.ndarray:
    """The one function request-handling code should call to embed a
    QUERY -- applies that model's instruction prefix, which a raw
    embed() call would otherwise miss. Returns a single (384,) vector."""
    config = MODEL_CONFIGS[model_key]
    return embed([config["query_prefix"] + text], model_key)[0]


_corpus_cache = {}


def _get_corpus(model_key):
    """
    Lazy-loads a model's precomputed corpus (scripts/build_semantic_index.py's
    output) once per process. Stored on disk as float16 (half the file
    size, no meaningful precision loss for cosine similarity); upcast
    to float32 here once, at load time, rather than on every search's
    dot product.
    """
    if model_key not in _corpus_cache:
        data_dir = MODEL_CONFIGS[model_key]["dir"] / "data"
        embeddings_path = data_dir / "corpus_embeddings.f16.npy"
        ids_path = data_dir / "corpus_ids.json"
        if not embeddings_path.exists():
            raise RuntimeError(
                f"{embeddings_path} not found -- run "
                f"scripts/build_semantic_index.py --model {model_key} first."
            )
        embeddings = np.load(embeddings_path).astype(np.float32)
        with open(ids_path) as f:
            ids = json.load(f)
        _corpus_cache[model_key] = (embeddings, ids)
    return _corpus_cache[model_key]


def _assign_confidence(results):
    """Same rank-percentile shape as recommender.py's own
    _assign_confidence() -- see this module's _CONFIDENCE_LEVELS
    comment for why it's reimplemented here rather than imported."""
    n = len(results)
    for position, result in enumerate(results):
        percentile_from_top = position / n if n else 0
        bucket_index = min(
            int(percentile_from_top * len(_CONFIDENCE_LEVELS)),
            len(_CONFIDENCE_LEVELS) - 1,
        )
        result["confidence"] = _CONFIDENCE_LEVELS[len(_CONFIDENCE_LEVELS) - 1 - bucket_index]


_EXPLANATIONS = {
    "en": "matched by AI semantic similarity between your text and this journal's profile, not a specific keyword match",
    "multilingual": "matched by AI semantic similarity (multilingual model, for Arabic/Indonesian text) between your text and this journal's profile, not a specific keyword match",
}


def search(query_text: str, top_n: int = 40) -> list[dict]:
    """
    Semantic search over the precomputed corpus -- routes to the
    English or multilingual model based on query_text's detected
    language (see route_model_key), embeds query_text with it, ranks
    every journal in THAT model's own corpus by cosine similarity
    (embeddings from the two models are not comparable to each other,
    so each model's ranking only ever runs against its own corpus),
    and returns the top_n as result dicts in the SAME shape
    services.recommender.JournalRecommender.recommend() produces (so
    web/templates/components/journal_card.html and everything
    downstream of it -- pagination, export, comparison -- works
    completely unchanged for either search path). The "explanation"
    field here is a fixed, honest sentence about semantic matching, not
    a keyword-hit list -- there ARE no keyword hits in this path, and
    fabricating field-specific ones would misrepresent how this result
    was actually found.

    No filter parameters (indexing/budget/quartile/languages/review
    time) yet -- this is the first, deliberately minimal version of
    this opt-in path (#143 follow-up); those can layer on as a
    follow-up once this core path is proven, without changing this
    function's shape.
    """
    model_key = route_model_key(query_text)
    corpus_embeddings, corpus_ids = _get_corpus(model_key)
    query_vec = embed_query(query_text, model_key)

    scores = corpus_embeddings @ query_vec
    top_n = min(top_n, len(corpus_ids))
    top_indices = np.argpartition(-scores, top_n - 1)[:top_n]
    top_indices = top_indices[np.argsort(-scores[top_indices])]

    ranked_ids = [corpus_ids[i] for i in top_indices]
    ranked_scores = {corpus_ids[i]: float(scores[i]) for i in top_indices}

    journals = get_journals_by_ids(ranked_ids)

    results = []
    for journal in journals:
        is_free = str(journal.apc).lower() == "no"
        usd_amount = None if is_free else parse_usd_amount(journal.apc_amount)
        score = ranked_scores[journal.id]

        results.append({
            "id": journal.id,
            "title": journal.title,
            "publisher": journal.publisher or "",
            "country": journal.country or "",
            "website": journal.website or "",
            "doaj_url": journal.doaj_url or "",
            "issn_print": journal.issn_print or "",
            "issn_online": journal.issn_online or "",
            "subjects": journal.subjects or "",
            "languages": journal.languages or "",
            "license": journal.license or "",
            "apc": journal.apc or "",
            "apc_amount": usd_amount,
            "is_free": is_free,
            "review_weeks": int(journal.review_weeks) if journal.review_weeks is not None else None,
            "sources": journal.sources,
            "source_details": journal.source_details,
            "enrichment": journal.enrichment,
            "aliases": journal.aliases,
            "publication_type_badge": format_publication_type_badge(journal),
            "score": score,
            "normalized_score": (score + 1) / 2,  # cosine similarity [-1,1] -> [0,1], for display parity only
            "explanation": _EXPLANATIONS[model_key],
        })

    _assign_confidence(results)
    return results
