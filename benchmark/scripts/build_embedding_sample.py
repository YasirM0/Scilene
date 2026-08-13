"""
Representative journal sample for benchmark/scripts/evaluate_embeddings.py
(#143 follow-up) -- embedding all 55,745 journals against every
candidate model was too slow to be practical on this box's CPU (a
single 137M-parameter model took well over an hour for the full
corpus). Building ONE fixed sample once and reusing it across every
model/corpus-variant run keeps every comparison apples-to-apples.

Always includes every journal referenced as a ground-truth target in
the benchmark dataset -- excluding one would make recall artificially
0 for that record regardless of how good a model actually is -- plus a
random fill up to --sample-size, seeded for reproducibility.

Run from the project root:
    python3 -m benchmark.scripts.build_embedding_sample \
        --dataset benchmark/datasets/dataset_20260808_133453.json \
        --sample-size 14000 \
        --output benchmark/datasets/embedding_sample_ids.json
"""

import argparse
import json
import random

from services.repository import get_connection


def run(dataset_path, sample_size, seed, output_path):
    with open(dataset_path) as f:
        dataset = json.load(f)
    target_ids = sorted({record["journal_id"] for record in dataset["records"]})
    target_id_set = set(target_ids)

    conn = get_connection()
    all_ids = [row[0] for row in conn.execute("SELECT id FROM journals").fetchall()]
    conn.close()

    if sample_size >= len(all_ids):
        sample_ids = sorted(all_ids)
    else:
        remaining_pool = [jid for jid in all_ids if jid not in target_id_set]
        fill_size = max(0, sample_size - len(target_ids))
        rng = random.Random(seed)
        fill = rng.sample(remaining_pool, min(fill_size, len(remaining_pool)))
        sample_ids = sorted(target_id_set | set(fill))

    payload = {
        "dataset_version": dataset["version"],
        "seed": seed,
        "requested_sample_size": sample_size,
        "num_target_journals": len(target_ids),
        "num_journal_ids": len(sample_ids),
        "journal_ids": sample_ids,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f)

    print(
        f"Sample: {len(sample_ids)} journals ({len(target_ids)} guaranteed targets + "
        f"{len(sample_ids) - len(target_ids)} random fill, seed={seed}) -> {output_path}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.dataset, args.sample_size, args.seed, args.output)


if __name__ == "__main__":
    main()
