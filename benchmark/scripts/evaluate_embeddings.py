"""
Ad-hoc embedding-model evaluation against the #112 benchmark harness.

NOT wired into the shipped app or services/recommender.py -- this is a
research/comparison tool for deciding whether (and which) embedding
model is worth building a real semantic layer around later (#115-125).
Reuses the exact scoring functions from benchmark/scripts/evaluate.py
(_rank_of/_score_ranking/_aggregate) so results are directly
comparable to the recommender/TF-IDF numbers already in
benchmark/results/.

Corpus (--corpus-variant):
  - "baseline": the same (title + subjects + keywords) text as the
    TF-IDF baseline (benchmark/baselines/tfidf.py's
    build_journal_corpus) -- what the TF-IDF baseline and the real
    recommender both search against today.
  - "openalex_topics": title/subjects/keywords replaced by real
    OpenAlex Topics for journals the fetcher (
    benchmark/scripts/fetch_openalex_topics.py) matched, falling back
    to the baseline text for any journal it didn't -- a proxy for the
    curated "index terms" field #73/#74 will eventually add, since
    that dataset doesn't exist yet.

--sample-file restricts the corpus to a fixed subset (see
build_embedding_sample.py) -- embedding the full 55,745-journal corpus
took over an hour per model on this box's CPU, impractical across
several candidate models.

Usage:
    python3 -m benchmark.scripts.evaluate_embeddings \
        --model nomic-ai/nomic-embed-text-v1.5 \
        --dataset benchmark/datasets/dataset_20260808_133453.json \
        --cache-dir /path/to/scratch \
        --sample-file benchmark/datasets/embedding_sample_ids.json \
        --corpus-variant baseline
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from benchmark.baselines.tfidf import build_journal_corpus
from benchmark.scripts.evaluate import _aggregate, _score_ranking, RECALL_KS, TOP_N
from services.app_info import APP_VERSION
from services.repository import get_connection

# Each model's sentence-transformers usage differs (plain text prefix
# vs. a named prompt vs. an instruction-style prefix) -- resolved here
# rather than guessed generically, since getting this wrong silently
# produces worse-than-real numbers for a model (see each model's own
# README/model card for what's used here). `trust_remote_code` is only
# set True where the model's own card requires it (custom architecture
# code shipped alongside the weights).
MODEL_CONFIGS = {
    "nomic-ai/nomic-embed-text-v1.5": {
        "doc_prefix": "search_document: ",
        "query_prefix": "search_query: ",
        "query_prompt_name": None,
        "trust_remote_code": False,
    },
    "microsoft/harrier-oss-v1-270m": {
        "doc_prefix": "",
        "query_prefix": "",
        "query_prompt_name": "web_search_query",
        "trust_remote_code": False,
    },
    # 137M params, same size class as nomic-v1.5 -- a same-weight-class
    # comparison point. Long-context variant (up to 8192 tokens) is
    # overkill for this corpus's short documents, but it's the same
    # checkpoint family Snowflake recommends for general retrieval.
    "Snowflake/snowflake-arctic-embed-m-long": {
        "doc_prefix": "",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "query_prompt_name": None,
        "trust_remote_code": True,
    },
    # Instruction-tuned retrieval models, 200+ language claim (relevant
    # given Scilene's EN/AR/ID UI) -- instruction text applies to
    # queries only, per the model card.
    "codefuse-ai/F2LLM-v2-160M": {
        "doc_prefix": "",
        "query_prefix": "Instruct: Given a question, retrieve passages that can help answer the question.\nQuery: ",
        "query_prompt_name": None,
        "trust_remote_code": False,
    },
    "codefuse-ai/F2LLM-v2-80M": {
        "doc_prefix": "",
        "query_prefix": "Instruct: Given a question, retrieve passages that can help answer the question.\nQuery: ",
        "query_prompt_name": None,
        "trust_remote_code": False,
    },
    # Multilingual (~100 languages, MoE: 475M total / 305M active) --
    # the one candidate here actually built for multilingual retrieval,
    # directly relevant to Scilene's EN/AR/ID journal search. Heaviest
    # model in this set; included as the "how much does going bigger +
    # multilingual-native actually buy us" comparison point.
    "nomic-ai/nomic-embed-text-v2-moe": {
        "doc_prefix": "search_document: ",
        "query_prefix": "search_query: ",
        "query_prompt_name": None,
        "trust_remote_code": True,
    },
    # #143 follow-up -- purpose-built small BERT-style encoders, added
    # after F2LLM-v2-80M (a causal/LLM-derived architecture repurposed
    # for embeddings) turned out SLOWER than 137M-parameter encoder
    # models despite having fewer parameters: architecture family
    # matters more than raw size for CPU throughput, and these two are
    # from the family (BERT-encoder, purpose-built for embeddings)
    # that's actually fast on CPU. Smaller than everything tested so
    # far (33M and 23M vs. the previous floor of 80M).
    "BAAI/bge-small-en-v1.5": {
        "doc_prefix": "",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "query_prompt_name": None,
        "trust_remote_code": False,
    },
    # No query/document distinction at all -- a symmetric model, unlike
    # every other candidate tested. Long-standing "fast baseline" for
    # exactly this reason.
    "sentence-transformers/all-MiniLM-L6-v2": {
        "doc_prefix": "",
        "query_prefix": "",
        "query_prompt_name": None,
        "trust_remote_code": False,
    },
}


def _encode(model, texts, prefix, prompt_name, batch_size, log_every=5000):
    if prefix:
        texts = [prefix + t for t in texts]

    embeddings = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start:start + batch_size]
        kwargs = {"batch_size": batch_size, "show_progress_bar": False, "normalize_embeddings": True}
        if prompt_name:
            kwargs["prompt_name"] = prompt_name
        embeddings.append(model.encode(chunk, **kwargs))
        if start % log_every < batch_size:
            print(f"  encoded {min(start + batch_size, len(texts))}/{len(texts)}", flush=True)

    return np.vstack(embeddings)


# Journal corpus text is short (median 51 chars, p99 336, but a rare
# outlier runs to ~1800) -- a handful of very long docs padding out an
# entire batch (attention memory scales with seq_len^2) is what caused
# a real out-of-memory/swap-thrashing run on this box's ~14GB RAM.
# Hard-capping both the raw text AND the tokenizer's max_seq_length
# keeps worst-case batch memory bounded regardless of what's in the DB.
MAX_CHARS = 400
MAX_SEQ_LENGTH = 128
QUERY_MAX_SEQ_LENGTH = 256
# Only 166 queries total, and query length is already hard-capped at
# QUERY_MAX_SEQ_LENGTH -- unlike the uncapped corpus text that caused
# the OOM above, worst-case query batch memory is already bounded
# regardless of this batch size, so it's safe to raise well past a
# single-outlier-safe minimum purely for throughput (was 8; the
# smaller value cost ~2 minutes of wall time per model for no
# corresponding safety benefit once the length cap already existed).
QUERY_BATCH_SIZE = 24


def _build_corpus(conn, sample_file, corpus_variant, openalex_cache):
    """
    Returns {journal_id: text}, restricted to --sample-file's journal
    IDs if given (see build_embedding_sample.py), using either the
    baseline (title+subjects+keywords) text or the OpenAlex-topics
    proxy for a future curated index-terms field (see
    fetch_openalex_topics.py) -- falling back to baseline text for any
    journal the fetcher had no OpenAlex match for, so no document in
    the openalex_topics variant is ever empty.
    """
    corpus = build_journal_corpus(conn)

    if sample_file:
        with open(sample_file) as f:
            journal_ids = json.load(f)["journal_ids"]
        corpus = {jid: corpus.get(jid, "") for jid in journal_ids}

    if corpus_variant == "baseline":
        return corpus

    with open(openalex_cache) as f:
        topics_cache = json.load(f)

    enriched, matched = {}, 0
    for jid, base_text in corpus.items():
        topics = topics_cache.get(str(jid))
        if not topics:
            enriched[jid] = base_text
            continue
        matched += 1
        topics_text = " ".join(topics)
        # "combined" keeps baseline's precise, narrow signal (exact
        # title/subject/keyword terms) AND adds openalex_topics' broad
        # thematic signal, instead of one replacing the other -- a
        # richer per-journal document than either alone.
        enriched[jid] = f"{base_text} {topics_text}" if corpus_variant == "combined" else topics_text
    print(
        f"{corpus_variant} corpus: {matched}/{len(corpus)} journals used real OpenAlex "
        f"topics ({len(corpus) - matched} fell back to baseline-only text)", flush=True,
    )
    return enriched


def run(model_name, dataset_path, cache_dir, batch_size, sample_file=None, corpus_variant="baseline", openalex_cache=None):
    if model_name not in MODEL_CONFIGS:
        raise SystemExit(f"No known prefix/prompt config for {model_name!r} -- add one to MODEL_CONFIGS.")
    config = MODEL_CONFIGS[model_name]
    if corpus_variant in ("openalex_topics", "combined") and not openalex_cache:
        raise SystemExit(f"--corpus-variant {corpus_variant} requires --openalex-cache")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{model_name.replace('/', '__')}__{corpus_variant}"

    import torch
    from sentence_transformers import SentenceTransformer

    print(f"Loading {model_name} ...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(model_name, trust_remote_code=config["trust_remote_code"])
    model.max_seq_length = MAX_SEQ_LENGTH
    load_seconds = time.time() - t0
    param_count = sum(p.numel() for p in model.parameters())
    print(f"Loaded in {load_seconds:.1f}s -- {param_count / 1e6:.0f}M parameters", flush=True)

    conn = get_connection()
    corpus = _build_corpus(conn, sample_file, corpus_variant, openalex_cache)
    conn.close()

    journal_ids = list(corpus.keys())
    journal_texts = [(corpus[jid] or "")[:MAX_CHARS] for jid in journal_ids]

    print(f"Encoding {len(journal_texts)} journal documents ...", flush=True)
    t0 = time.time()
    corpus_embeddings = _encode(model, journal_texts, config["doc_prefix"], None, batch_size)
    corpus_seconds = time.time() - t0
    corpus_docs_per_sec = len(journal_texts) / corpus_seconds
    print(f"Corpus encoded in {corpus_seconds:.1f}s ({corpus_docs_per_sec:.1f} docs/sec)", flush=True)

    np.save(cache_dir / f"{safe_name}__corpus_embeddings.npy", corpus_embeddings)
    with open(cache_dir / f"{safe_name}__corpus_ids.json", "w") as f:
        json.dump(journal_ids, f)

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    records = dataset["records"]

    query_texts = [r["abstract"] for r in records]
    print(f"Encoding {len(query_texts)} benchmark query abstracts ...", flush=True)
    # Only 166 of these (vs. 55,745 corpus docs) -- affordable to keep
    # more of each real abstract than the corpus's short-text cap,
    # with a small batch size so no single long outlier dominates a
    # batch's padded tensor size.
    model.max_seq_length = QUERY_MAX_SEQ_LENGTH
    t0 = time.time()
    query_embeddings = _encode(
        model, query_texts, config["query_prefix"], config["query_prompt_name"],
        min(batch_size, QUERY_BATCH_SIZE),
    )
    query_seconds = time.time() - t0
    query_docs_per_sec = len(query_texts) / query_seconds
    print(f"Queries encoded in {query_seconds:.1f}s ({query_docs_per_sec:.1f} docs/sec)", flush=True)

    id_to_index = {jid: i for i, jid in enumerate(journal_ids)}

    per_record_recall, per_record_rr = [], []
    for record, query_vec in zip(records, query_embeddings):
        scores = corpus_embeddings @ query_vec
        top_indices = np.argpartition(-scores, TOP_N)[:TOP_N]
        top_indices = top_indices[np.argsort(-scores[top_indices])]
        ranked_ids = [journal_ids[i] for i in top_indices]

        target_id = record["journal_id"]
        hits, rr = _score_ranking(ranked_ids, target_id)
        per_record_recall.append(hits)
        per_record_rr.append(rr)

    metrics = _aggregate(per_record_recall, per_record_rr, len(records))

    report = {
        "model": model_name,
        "corpus_variant": corpus_variant,
        "sample_file": str(sample_file) if sample_file else None,
        "parameter_count": param_count,
        "embedding_dim": int(corpus_embeddings.shape[1]),
        "dataset_version": dataset["version"],
        "dataset_path": str(dataset_path),
        "num_records_evaluated": len(records),
        "recommendation_engine_version": APP_VERSION,
        "timing": {
            "load_seconds": round(load_seconds, 2),
            "corpus_docs": len(journal_texts),
            "corpus_encode_seconds": round(corpus_seconds, 2),
            "corpus_docs_per_sec": round(corpus_docs_per_sec, 2),
            "query_docs_per_sec": round(query_docs_per_sec, 2),
            "torch_threads": torch.get_num_threads(),
        },
        "metrics": metrics,
    }

    result_path = cache_dir / f"{safe_name}__report.json"
    with open(result_path, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\nReport written to {result_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=list(MODEL_CONFIGS.keys()))
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--sample-file", default=None, help="Restrict corpus to these journal IDs (build_embedding_sample.py)")
    parser.add_argument("--corpus-variant", choices=["baseline", "openalex_topics", "combined"], default="baseline")
    parser.add_argument("--openalex-cache", default=None, help="Required if --corpus-variant openalex_topics")
    args = parser.parse_args()

    run(
        args.model, args.dataset, args.cache_dir, args.batch_size,
        sample_file=args.sample_file, corpus_variant=args.corpus_variant, openalex_cache=args.openalex_cache,
    )


if __name__ == "__main__":
    main()
