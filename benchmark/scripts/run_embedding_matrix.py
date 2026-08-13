"""
Two-stage orchestration for the full embedding-model comparison (#143
follow-up): builds the representative journal sample, fetches the
OpenAlex-topics proxy corpus (concurrently -- see
fetch_openalex_topics.py), then evaluates every model in
evaluate_embeddings.MODEL_CONFIGS against both corpus variants
(baseline, openalex_topics).

Two stages, not one flat pass over the full sample, to avoid spending
the same expensive full-scale evaluation on combinations a cheap
screening pass already shows are clearly behind:

  Stage 1 (screen): every (model, corpus_variant) combination against
    a SMALL subset of the full sample -- fast, rules out weak
    combinations cheaply.
  Stage 2 (confirm): only the top --top-n combinations from Stage 1,
    re-evaluated against the FULL sample for the authoritative,
    statistically solid numbers that actually inform the final
    recommendation. Nothing about the winning combination's own
    result is ever based on the smaller Stage 1 sample -- Stage 1
    only decides which combinations are worth Stage 2's cost, it
    never substitutes for it.

A model failing to load or encode is recorded as an error entry, not
an aborted run -- one bad model shouldn't lose results already
collected for the others.

Run from the project root:
    python3 -m benchmark.scripts.run_embedding_matrix \
        --dataset benchmark/datasets/dataset_20260808_133453.json \
        --sample-size 14000 \
        --stage1-sample-size 2500 \
        --top-n 3 \
        --cache-dir /path/to/scratch
"""

import argparse
import json
import random
import time
import traceback
from pathlib import Path

from benchmark.scripts import build_embedding_sample, fetch_openalex_topics, evaluate_embeddings

CORPUS_VARIANTS = ["baseline", "openalex_topics"]


def _build_stage1_sample(full_sample_file, stage1_size, seed, output_path):
    """
    A deterministic SUBSET of the already-built full sample -- not a
    fresh independent sample -- so the same openalex_topics_cache.json
    (fetched once for the full sample) covers Stage 1 too, with no
    second fetch. Still guarantees every benchmark target journal is
    included, same reasoning as build_embedding_sample.py.
    """
    with open(full_sample_file) as f:
        full = json.load(f)
    full_ids = full["journal_ids"]

    if stage1_size >= len(full_ids):
        stage1_ids = full_ids
    else:
        # A plain seeded random subset -- doesn't itself guarantee
        # every benchmark target journal survives the subsample (the
        # full sample's own list is target IDs unioned with random
        # fill, then re-sorted, so target/fill order isn't preserved
        # to slice against). _ensure_targets_included() re-adds any
        # missing targets right after this call, from the dataset
        # directly, rather than relying on this sample's internal
        # ordering.
        rng = random.Random(seed)
        stage1_ids = rng.sample(full_ids, stage1_size)

    payload = {
        "source_sample_file": str(full_sample_file),
        "seed": seed,
        "num_journal_ids": len(stage1_ids),
        "journal_ids": sorted(stage1_ids),
    }
    with open(output_path, "w") as f:
        json.dump(payload, f)
    print(f"Stage 1 sample: {len(stage1_ids)} journals (subset of the full sample) -> {output_path}", flush=True)


def _ensure_targets_included(stage1_sample_file, dataset_path):
    """
    Guarantees every benchmark target journal is in the Stage 1
    sample too (a random subset of the full sample could otherwise
    exclude some, artificially zeroing their recall in Stage 1 --
    harmless for Stage 2's final numbers since Stage 2 always uses the
    full sample, but would make Stage 1's screening ranking noisier
    than necessary).
    """
    with open(dataset_path) as f:
        dataset = json.load(f)
    target_ids = {record["journal_id"] for record in dataset["records"]}

    with open(stage1_sample_file) as f:
        payload = json.load(f)
    merged = sorted(set(payload["journal_ids"]) | target_ids)
    payload["journal_ids"] = merged
    payload["num_journal_ids"] = len(merged)
    with open(stage1_sample_file, "w") as f:
        json.dump(payload, f)


def _run_combo(model_name, corpus_variant, dataset_path, cache_dir, batch_size, sample_file, openalex_cache):
    t0 = time.time()
    try:
        report = evaluate_embeddings.run(
            model_name, dataset_path, cache_dir, batch_size,
            sample_file=sample_file, corpus_variant=corpus_variant,
            openalex_cache=openalex_cache if corpus_variant == "openalex_topics" else None,
        )
        report["wall_seconds"] = round(time.time() - t0, 1)
        return report
    except Exception as exc:
        print(f"FAILED: {model_name} / {corpus_variant}: {exc}", flush=True)
        traceback.print_exc()
        return {
            "model": model_name,
            "corpus_variant": corpus_variant,
            "error": str(exc),
            "wall_seconds": round(time.time() - t0, 1),
        }


def _rank_key(report):
    """Higher is better. recall@10 is the primary signal (matches how
    docs/BENCHMARK.md already reports headline numbers); MRR breaks ties."""
    metrics = report.get("metrics") or {}
    return (metrics.get("recall@10", 0.0), metrics.get("mrr", 0.0))


def run(dataset_path, sample_size, stage1_sample_size, top_n, cache_dir, mailto, batch_size):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    full_sample_file = cache_dir / "embedding_sample_ids.json"
    if not full_sample_file.exists():
        print("=== Building full representative sample ===", flush=True)
        build_embedding_sample.run(dataset_path, sample_size, 42, full_sample_file)
    else:
        print(f"Reusing existing full sample: {full_sample_file}", flush=True)

    openalex_cache = cache_dir / "openalex_topics_cache.json"
    print("\n=== Fetching OpenAlex topics for the FULL sample (resumable, concurrent) ===", flush=True)
    fetch_openalex_topics.run(full_sample_file, openalex_cache, mailto, workers=60)

    stage1_sample_file = cache_dir / "embedding_stage1_sample_ids.json"
    if not stage1_sample_file.exists():
        print("\n=== Building Stage 1 screening sample (subset of the full sample) ===", flush=True)
        _build_stage1_sample(full_sample_file, stage1_sample_size, 42, stage1_sample_file)
        _ensure_targets_included(stage1_sample_file, dataset_path)
    else:
        print(f"Reusing existing Stage 1 sample: {stage1_sample_file}", flush=True)

    models = list(evaluate_embeddings.MODEL_CONFIGS.keys())
    combos = [(m, v) for m in models for v in CORPUS_VARIANTS]

    print(f"\n=== Stage 1: screening {len(combos)} (model, corpus_variant) combinations ===", flush=True)
    stage1_results = []
    for index, (model_name, corpus_variant) in enumerate(combos, start=1):
        print(f"\n--- Stage 1 [{index}/{len(combos)}] {model_name} / {corpus_variant} ---", flush=True)
        report = _run_combo(
            model_name, corpus_variant, dataset_path, cache_dir, batch_size,
            stage1_sample_file, openalex_cache,
        )
        report["stage"] = 1
        stage1_results.append(report)
        with open(cache_dir / "stage1_results.json", "w") as f:
            json.dump(stage1_results, f, indent=2)

    ranked = sorted((r for r in stage1_results if "error" not in r), key=_rank_key, reverse=True)
    top_combos = [(r["model"], r["corpus_variant"]) for r in ranked[:top_n]]
    print(
        f"\n=== Stage 1 complete. Top {len(top_combos)} combos advancing to Stage 2 "
        f"(full sample): {top_combos} ===", flush=True,
    )

    print(f"\n=== Stage 2: confirming top {len(top_combos)} combos on the FULL sample ===", flush=True)
    stage2_results = []
    for index, (model_name, corpus_variant) in enumerate(top_combos, start=1):
        print(f"\n--- Stage 2 [{index}/{len(top_combos)}] {model_name} / {corpus_variant} ---", flush=True)
        report = _run_combo(
            model_name, corpus_variant, dataset_path, cache_dir, batch_size,
            full_sample_file, openalex_cache,
        )
        report["stage"] = 2
        stage2_results.append(report)
        with open(cache_dir / "stage2_results.json", "w") as f:
            json.dump(stage2_results, f, indent=2)

    combined = {"stage1_results": stage1_results, "stage2_results": stage2_results}
    with open(cache_dir / "matrix_results.json", "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\nAll runs complete. Combined results: {cache_dir / 'matrix_results.json'}")
    return combined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--stage1-sample-size", type=int, required=True)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--mailto", default=None)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    run(
        args.dataset, args.sample_size, args.stage1_sample_size, args.top_n,
        args.cache_dir, args.mailto, args.batch_size,
    )


if __name__ == "__main__":
    main()
