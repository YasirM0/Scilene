"""
Hybrid dense (embedding) + sparse (TF-IDF) retrieval fusion (#143
follow-up) -- checks whether combining bge-small-en-v1.5's embedding
ranking with the existing TF-IDF baseline's ranking raises Recall@10
over either alone. Dense and sparse retrieval catch different things
(semantic similarity vs. exact term overlap), so fusing them is a
well-established way to improve recall without needing a bigger or
slower model.

Reuses bge-small's ALREADY-CACHED corpus embeddings from a prior
evaluate_embeddings.py run (see --corpus-embeddings/--corpus-ids) --
only re-encodes the 166 (cheap) queries, and builds a fresh in-memory
TF-IDF index over the identical sampled corpus (baseline text, the
same text the TF-IDF baseline normally searches). No corpus
re-embedding, so this runs in under a minute rather than several.

Fusion: Reciprocal Rank Fusion (RRF), score(doc) = sum over each
ranking of 1/(k + rank_in_that_ranking), k=60 (the standard RRF
constant) -- simple, has no score-scale-normalization issues (unlike
a raw weighted sum of cosine similarity and TF-IDF scores, which live
on different scales), and is the most common choice in IR literature
for exactly this kind of two-ranker fusion.

Run from the project root:
    python3 -m benchmark.scripts.evaluate_hybrid_fusion \
        --model BAAI/bge-small-en-v1.5 \
        --dataset benchmark/datasets/dataset_20260808_133453.json \
        --sample-file benchmark/results/embedding_evaluation_20260812/embedding_sample_ids.json \
        --corpus-embeddings /path/to/BAAI__bge-small-en-v1.5__openalex_topics__corpus_embeddings.npy \
        --corpus-ids /path/to/BAAI__bge-small-en-v1.5__openalex_topics__corpus_ids.json \
        --query-prefix "Represent this sentence for searching relevant passages: "
"""

import argparse
import json

import numpy as np

from benchmark.baselines.tfidf import TFIDFIndex, build_journal_corpus
from benchmark.scripts.evaluate import _aggregate, _score_ranking, RECALL_KS, TOP_N
from services.repository import get_connection

RRF_K = 60


def _rrf_scores(ranked_id_lists):
    """ranked_id_lists: list of [doc_id, ...] rankings (best first).
    Returns {doc_id: fused_score}, higher is better."""
    scores = {}
    for ranking in ranked_id_lists:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
    return scores


def run(model_name, dataset_path, sample_file, corpus_embeddings_path, corpus_ids_path, query_prefix, query_prompt_name):
    from sentence_transformers import SentenceTransformer

    with open(sample_file) as f:
        journal_ids_sample = json.load(f)["journal_ids"]

    conn = get_connection()
    baseline_corpus_full = build_journal_corpus(conn)
    conn.close()
    baseline_corpus = {jid: baseline_corpus_full.get(jid, "") for jid in journal_ids_sample}

    print("Building TF-IDF index over the sampled corpus ...", flush=True)
    tfidf_index = TFIDFIndex(baseline_corpus)

    corpus_embeddings = np.load(corpus_embeddings_path)
    with open(corpus_ids_path) as f:
        corpus_ids = json.load(f)
    print(f"Loaded {len(corpus_ids)} cached corpus embeddings from {corpus_embeddings_path}", flush=True)

    with open(dataset_path) as f:
        dataset = json.load(f)
    records = dataset["records"]

    print(f"Loading {model_name} to re-encode {len(records)} queries only ...", flush=True)
    model = SentenceTransformer(model_name)
    query_texts = [(query_prefix + r["abstract"]) for r in records]
    encode_kwargs = {"show_progress_bar": False, "normalize_embeddings": True}
    if query_prompt_name:
        encode_kwargs["prompt_name"] = query_prompt_name
    query_embeddings = model.encode(query_texts, batch_size=24, **encode_kwargs)

    dense_recall, dense_rr = [], []
    sparse_recall, sparse_rr = [], []
    fused_recall, fused_rr = [], []

    for record, query_vec, query_text in zip(records, query_embeddings, [r["abstract"] for r in records]):
        target_id = record["journal_id"]

        dense_scores = corpus_embeddings @ query_vec
        dense_top = np.argsort(-dense_scores)[:max(TOP_N, 200)]
        dense_ranked_ids = [corpus_ids[i] for i in dense_top]

        sparse_ranked_ids = [doc_id for doc_id, _ in tfidf_index.search(query_text, top_n=max(TOP_N, 200))]

        fused_scores = _rrf_scores([dense_ranked_ids, sparse_ranked_ids])
        fused_ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)[:TOP_N]

        for ranked_ids, recall_list, rr_list in (
            (dense_ranked_ids[:TOP_N], dense_recall, dense_rr),
            (sparse_ranked_ids[:TOP_N], sparse_recall, sparse_rr),
            (fused_ranked_ids, fused_recall, fused_rr),
        ):
            hits, rr = _score_ranking(ranked_ids, target_id)
            recall_list.append(hits)
            rr_list.append(rr)

    report = {
        "model": model_name,
        "fusion": "RRF(dense, sparse)",
        "rrf_k": RRF_K,
        "num_records_evaluated": len(records),
        "dense_only": _aggregate(dense_recall, dense_rr, len(records)),
        "sparse_only_tfidf": _aggregate(sparse_recall, sparse_rr, len(records)),
        "hybrid_fused": _aggregate(fused_recall, fused_rr, len(records)),
    }
    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sample-file", required=True)
    parser.add_argument("--corpus-embeddings", required=True)
    parser.add_argument("--corpus-ids", required=True)
    parser.add_argument("--query-prefix", default="")
    parser.add_argument("--query-prompt-name", default=None)
    args = parser.parse_args()

    run(
        args.model, args.dataset, args.sample_file, args.corpus_embeddings, args.corpus_ids,
        args.query_prefix, args.query_prompt_name,
    )


if __name__ == "__main__":
    main()
