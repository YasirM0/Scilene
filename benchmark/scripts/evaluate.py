"""
Benchmark evaluation (#112, docs/BENCHMARK.md).

For every record in a dataset built by build_dataset.py, runs the
record's abstract through:
  1. Scilene's real deterministic recommender
     (services.recommender.JournalRecommender.recommend) -- exactly
     what the app itself calls, no shortcuts.
  2. The standalone TF-IDF baseline (benchmark/baselines/tfidf.py).

...and checks whether the journal the paper was ACTUALLY published in
appears in each ranking's top 5 / 10 / 20 (Recall@k), plus the Mean
Reciprocal Rank (MRR) across the whole dataset. This never touches or
is touched by services/recommender.py's actual behavior -- it only
calls the same public recommend() the web app calls, read-only.

Run from the project root:
    python3 -m benchmark.scripts.evaluate benchmark/datasets/dataset_<...>.json

Output: a report printed to stdout and written to
benchmark/results/<dataset version>.json, per docs/BENCHMARK.md's
"Version History" (dataset version, recommendation engine version,
metrics).
"""

import argparse
import json
import sys
from pathlib import Path

from benchmark.baselines.tfidf import TFIDFIndex, build_journal_corpus
from services.app_info import APP_VERSION
from services.recommender import JournalRecommender
from services.repository import get_connection

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RECALL_KS = (5, 10, 20)
TOP_N = max(RECALL_KS)


def _rank_of(target_id, ranked_ids):
    """1-indexed rank of target_id in ranked_ids, or None if absent."""
    try:
        return ranked_ids.index(target_id) + 1
    except ValueError:
        return None


def _score_ranking(ranked_ids, target_id):
    rank = _rank_of(target_id, ranked_ids)
    recall_hits = {k: (rank is not None and rank <= k) for k in RECALL_KS}
    reciprocal_rank = (1.0 / rank) if rank else 0.0
    return recall_hits, reciprocal_rank


def _aggregate(per_record_recall, per_record_rr, n):
    if n == 0:
        return {f"recall@{k}": 0.0 for k in RECALL_KS} | {"mrr": 0.0}
    metrics = {
        f"recall@{k}": sum(hits[k] for hits in per_record_recall) / n
        for k in RECALL_KS
    }
    metrics["mrr"] = sum(per_record_rr) / n
    return metrics


def evaluate(dataset_path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    records = dataset["records"]
    if not records:
        print("Dataset has no records -- nothing to evaluate.", file=sys.stderr)
        return None

    conn = get_connection()
    corpus = build_journal_corpus(conn)
    conn.close()

    tfidf_index = TFIDFIndex(corpus)
    recommender = JournalRecommender()

    recommender_recall, recommender_rr = [], []
    baseline_recall, baseline_rr = [], []
    skipped = 0

    for i, record in enumerate(records, start=1):
        target_id = record["journal_id"]

        recs = recommender.recommend(title="", keywords=[], abstract=record["abstract"])
        if recs is None:
            recs = []
        ranked_ids = [r["id"] for r in recs[:TOP_N]]

        baseline_ranked = tfidf_index.search(record["abstract"], top_n=TOP_N)
        baseline_ids = [doc_id for doc_id, _score in baseline_ranked]

        if not ranked_ids and not baseline_ids:
            skipped += 1
            continue

        hits, rr = _score_ranking(ranked_ids, target_id)
        recommender_recall.append(hits)
        recommender_rr.append(rr)

        b_hits, b_rr = _score_ranking(baseline_ids, target_id)
        baseline_recall.append(b_hits)
        baseline_rr.append(b_rr)

        print(f"[{i}/{len(records)}] {record['journal_title'][:60]}", file=sys.stderr)

    n = len(recommender_recall)
    report = {
        "dataset_version": dataset["version"],
        "dataset_path": str(dataset_path),
        "num_records_evaluated": n,
        "num_records_skipped": skipped,
        "recommendation_engine_version": APP_VERSION,
        "recommender": _aggregate(recommender_recall, recommender_rr, n),
        "baseline_tfidf": _aggregate(baseline_recall, baseline_rr, n),
    }
    return report


def _print_report(report):
    print()
    print("=" * 60)
    print(f"Scilene Benchmark -- dataset {report['dataset_version']}")
    print("=" * 60)
    print(f"Records evaluated: {report['num_records_evaluated']} "
          f"(skipped: {report['num_records_skipped']})")
    print(f"Recommendation engine version: {report['recommendation_engine_version']}")
    print()
    print(f"{'Metric':<12}{'Recommender':>15}{'TF-IDF baseline':>18}")
    for key in [f"recall@{k}" for k in RECALL_KS] + ["mrr"]:
        rec_val = report["recommender"][key]
        base_val = report["baseline_tfidf"][key]
        print(f"{key:<12}{rec_val:>15.3f}{base_val:>18.3f}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="Path to a dataset JSON built by build_dataset.py")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    report = evaluate(dataset_path)
    if report is None:
        return

    _print_report(report)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / f"{report['dataset_version']}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to {result_path}")


if __name__ == "__main__":
    main()
