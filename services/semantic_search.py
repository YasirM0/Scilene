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

One model: sentence-transformers/all-MiniLM-L12-v2, run on real
curated index terms (#73/#74) as the corpus text -- see
scripts/build_semantic_index.py. Replaces the original
bge-small-en-v1.5 (best of 8 candidates benchmarked at the time,
against an OpenAlex-topics proxy corpus, since real index terms
didn't exist yet). all-MiniLM-L12-v2 has the same 384-dim embeddings
as bge-small (33.8MB quantized) and ships as a pre-quantized official
ONNX export (34.1MB, no manual quantization work needed).

Arabic/Indonesian queries no longer reach this module's language
routing at all -- that whole approach (a second model,
multilingual-e5-small, quantized + vocabulary-trimmed to fit
deployment budgets, searching a separate OpenAlex-topics-proxy corpus)
was tried, shipped, and then REMOVED once real curated index terms
made a translate-to-English + single-model approach clearly better in
a direct A/B test (see docs/experiments/embedding_benchmarks.md for
the full history of both the multilingual routing work and why it was
superseded). Non-English query handling now happens BEFORE a query
ever reaches this module -- see services/query_translator.py:
Indonesian gets dictionary-translated to English, Arabic is blocked
with a "use the desktop app" message. This module is English-only by
design, not by accident.

Runs entirely locally -- no external API calls at request time,
matching the same "local, indexed database" philosophy the existing
keyword search already advertises. Model files live under models/
(committed directly to the repo, same convention as
data/journal_intelligence.db -- see that file's own git history for
precedent).
"""

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from services.recommender import parse_usd_amount
from services.repository import get_journals_by_ids, filtered_journal_ids
from services.stopwords import filter_stopwords
from services.subject_taxonomy import journal_ids_for_categories
from utils.publication_types import format_publication_type_badge

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "all-MiniLM-L12-v2-onnx"
CORPUS_EMBEDDINGS_PATH = MODEL_DIR / "data" / "corpus_embeddings.f16.npy"
CORPUS_IDS_PATH = MODEL_DIR / "data" / "corpus_ids.json"
CORPUS_META_PATH = MODEL_DIR / "data" / "corpus_meta.json"

# Symmetric model -- no query/document instruction prefix, unlike
# bge-small/e5 (both asymmetric retrieval models used previously).
# Getting this right matters the same way pooling does: adding a
# prefix here wouldn't error, just silently make results worse.
QUERY_PREFIX = ""
MAX_SEQ_LENGTH = 128  # sentence_bert_config.json's own trained limit
PAD_ID = 0
PAD_TOKEN = "[PAD]"

# Percentile-based, same shape as (but NOT imported from)
# services/recommender.py's own _assign_confidence() -- consistent
# visual language for the user (same five tiers, same "top fifth of
# THIS search's own results" relativity) without semantic_search.py
# importing scoring logic from the deterministic engine, or vice
# versa. Cosine similarity and the recommender's keyword-hit score are
# different metrics on different scales; only the RANK-based bucketing
# approach carries over, not any numeric threshold.
_CONFIDENCE_LEVELS = ("Poor", "Weak", "Moderate", "Strong", "Excellent")

_tokenizer = None
_session = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        _tokenizer.enable_padding(pad_id=PAD_ID, pad_token=PAD_TOKEN)
        _tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)
    return _tokenizer


def _get_session():
    # Lazy singleton -- loaded on first actual use (not at import
    # time, let alone app startup), so nothing pays this cost unless
    # the opt-in semantic search path is actually exercised.
    global _session
    if _session is None:
        opts = ort.SessionOptions()
        opts.enable_cpu_mem_arena = False
        opts.enable_mem_pattern = False
        _session = ort.InferenceSession(
            str(MODEL_DIR / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"]
        )
    return _session


def embed(texts: list[str]) -> np.ndarray:
    """
    L2-normalized embeddings for a batch of strings, shape (N, 384).
    Mean pooling, attention-mask-weighted -- padded positions must not
    count toward the average (see the model's own card).
    """
    tokenizer = _get_tokenizer()
    session = _get_session()

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

    mask = attention_mask[:, :, None].astype(np.float32)
    summed = (last_hidden * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    pooled = summed / counts

    norm = np.linalg.norm(pooled, axis=1, keepdims=True)
    return pooled / norm


def embed_query(text: str) -> np.ndarray:
    """The one function request-handling code should call to embed a
    QUERY -- applies the (currently empty) instruction prefix, for
    parity with the doc-embedding path. Returns a single (384,) vector."""
    return embed([QUERY_PREFIX + text])[0]


_corpus_embeddings = None
_corpus_ids = None


def _get_corpus():
    """
    Lazy-loads the precomputed corpus (scripts/build_semantic_index.py's
    output) once per process. Stored on disk as float16 (half the file
    size, no meaningful precision loss for cosine similarity); upcast
    to float32 here once, at load time, rather than on every search's
    dot product.
    """
    global _corpus_embeddings, _corpus_ids
    if _corpus_embeddings is None:
        if not CORPUS_EMBEDDINGS_PATH.exists():
            raise RuntimeError(
                f"{CORPUS_EMBEDDINGS_PATH} not found -- run "
                f"scripts/build_semantic_index.py first."
            )
        _corpus_embeddings = np.load(CORPUS_EMBEDDINGS_PATH).astype(np.float32)
        with open(CORPUS_IDS_PATH) as f:
            _corpus_ids = json.load(f)
    return _corpus_embeddings, _corpus_ids


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


_EXPLANATION = "matched by AI semantic similarity between your text and this journal's profile, not a specific keyword match"


def _query_terms(query_text):
    """
    Same tokenization services/recommender.py uses for its own
    title+abstract fallback -- plain word splitting, stopwords
    removed, >3 chars -- so #81's "shares these subjects" note below
    uses the same notion of "a real word from your query" the
    deterministic engine already does, not a new one invented here.
    """
    words = filter_stopwords([
        word.strip(".,;:()").lower()
        for word in query_text.split()
        if len(word.strip(".,;:()")) > 3
    ])
    seen = set()
    terms = []
    for word in words:
        if word not in seen:
            seen.add(word)
            terms.append(word)
    return terms


def _join_terms(terms):
    if len(terms) == 1:
        return terms[0]
    if len(terms) == 2:
        return f"{terms[0]} and {terms[1]}"
    return ", ".join(terms[:-1]) + f", and {terms[-1]}"


def _explanation_for(query_text, subjects, title="", keywords=""):
    """
    #81 ("Recommendation Explanations from Scope & Focus") landed on
    this as its redefinition: journals.index_terms only ever exists as
    an embedding, never as retrievable text (see this module's own
    SECURITY note), so an explanation can't quote the terms that
    actually drove the ranking -- an embedding model has no generative
    capability at all, it only ever outputs a similarity number, so
    there is no path to a genuine per-journal "why" sentence the way
    services/explain.py's deterministic engine produces one (that
    would need a real LLM, out of scope -- see docs/AI_ARCHITECTURE.md).
    This surfaces overlap with a journal's PUBLIC subjects/title/
    keywords fields instead -- purely additive to _EXPLANATION, never a
    substitute for it. The ranking itself came from embedding
    similarity, not these specific word hits, so this never claims
    otherwise; it's supplementary context on data already shown
    elsewhere on the card, not a description of how the AI ranked it.

    Checks subjects, then title, then keywords -- same field priority
    as services/explain.py's build_explanation(), so both search
    engines surface the strongest available signal first. Only the
    first field with a hit is shown, matching build_explanation()'s
    one-reason-at-a-time shape rather than stacking every overlap.
    """
    terms = _query_terms(query_text)
    if not terms:
        return _EXPLANATION

    if subjects:
        hits = [t for t in terms if t in subjects.lower()][:5]
        if hits:
            return f"{_EXPLANATION}. It also lists {_join_terms(hits)} among its subjects."

    if title:
        hits = [t for t in terms if t in title.lower()][:5]
        if hits:
            return f"{_EXPLANATION}. Its title also mentions {_join_terms(hits)}."

    if keywords:
        hits = [t for t in terms if t in keywords.lower()][:5]
        if hits:
            return f"{_EXPLANATION}. It's also tagged with {_join_terms(hits)}."

    return _EXPLANATION


def corpus_coverage():
    """
    Journal counts for the Statistics dashboard (#60 follow-up).
    `total_journals` is derivable from corpus_ids.json alone (just IDs,
    no security concern) the moment ANY corpus has been built at all.
    `curated_index_terms` additionally needs corpus_meta.json, written
    by scripts/build_semantic_index.py alongside the embeddings -- a
    corpus built before that file existed (true of the database
    currently shipped, built before this feature) won't have it, so
    it's None here rather than making the whole stat unavailable over
    one missing number. Counts only, never the terms themselves --
    safe to read even though journals.index_terms itself is wiped from
    the database (see this module's docstring). Returns None only if
    no corpus has been built at all (dev checkout without the model
    data), so the dashboard can omit the stat entirely in that case.
    """
    if not CORPUS_IDS_PATH.exists():
        return None

    with open(CORPUS_IDS_PATH) as f:
        total_journals = len(json.load(f))

    curated_index_terms = None
    if CORPUS_META_PATH.exists():
        with open(CORPUS_META_PATH) as f:
            curated_index_terms = json.load(f).get("curated_index_terms")

    return {"total_journals": total_journals, "curated_index_terms": curated_index_terms}


def search(query_text: str, top_n: int = 40, languages=None, free_only=False, min_budget=None,
           max_budget=None, indexing=None, quartiles=None, sinta_levels=None, max_review_weeks=None,
           categories=None) -> list[dict]:
    """
    Semantic search over the precomputed corpus -- embeds query_text,
    ranks every journal by cosine similarity, and returns the top_n as
    result dicts in the SAME shape services.recommender.JournalRecommender
    .recommend() produces (so web/templates/components/journal_card.html
    and everything downstream of it -- pagination, export, comparison --
    works completely unchanged for either search path). The "explanation"
    field here always leads with a fixed, honest sentence about
    semantic matching -- the ranking itself came from embedding
    similarity, not a keyword hit, and fabricating a claim otherwise
    would misrepresent how this result was actually found. See
    _explanation_for()'s own docstring for the real, additive overlap
    check appended to it (subjects/title/keywords), which is honest
    supplementary context, not a description of how the AI ranked it.

    Callers are expected to have already handled non-English input --
    see services/query_translator.py -- this function assumes
    query_text is English.

    Filters (#144) mask the corpus BEFORE ranking, not the results
    after -- so top_n always returns up to top_n *eligible* journals,
    never fewer because some of a fixed-size ranked slate got filtered
    out afterward. services.repository.filtered_journal_ids() reuses
    the exact same filter dimensions/SQL patterns
    services.repository.search_candidates() (the deterministic path)
    already uses, so "Q1 only" or "free only" means the same thing on
    either search strategy.

    `categories` (#79) -- subject/field names from
    services.subject_taxonomy.all_categories(); resolved to an id set
    here (not inside filtered_journal_ids(), which would need to
    import subject_taxonomy and create a circular import -- see that
    module's own docstring) and passed through as `restrict_to_ids`.
    """
    corpus_embeddings, corpus_ids = _get_corpus()
    query_vec = embed_query(query_text)

    restrict_to_ids = journal_ids_for_categories(categories) if categories else None
    allowed_ids = filtered_journal_ids(
        languages=languages, free_only=free_only, min_budget=min_budget, max_budget=max_budget,
        indexing=indexing, quartiles=quartiles, sinta_levels=sinta_levels, max_review_weeks=max_review_weeks,
        restrict_to_ids=restrict_to_ids,
    )

    scores = corpus_embeddings @ query_vec
    if allowed_ids is not None:
        mask = np.array([cid in allowed_ids for cid in corpus_ids])
        scores = np.where(mask, scores, -np.inf)

    top_n = min(top_n, len(corpus_ids))
    top_indices = np.argpartition(-scores, top_n - 1)[:top_n]
    top_indices = top_indices[np.argsort(-scores[top_indices])]
    # -inf-scored (filtered-out) slots can still land in the raw
    # top_n if fewer than top_n journals pass the filter -- drop them
    # rather than return a journal the filter explicitly excluded.
    top_indices = [i for i in top_indices if scores[i] != -np.inf]

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
            "explanation": _explanation_for(query_text, journal.subjects, journal.title, journal.keywords),
        })

    _assign_confidence(results)
    return results
