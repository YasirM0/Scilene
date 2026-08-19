"""
Builds a model's semantic search corpus embeddings (#143 follow-up,
multilingual follow-up) -- every journal's "combined" text
(title+subjects+keywords, same as the existing keyword search,
concatenated with real OpenAlex Topics) embedded with the given
model via services/semantic_search.py.

One-time (or run-after-a-database-rebuild, or after adding a new
model) offline step. Output is committed directly to the repo
(models/<model>/data/), same convention as data/journal_intelligence.db
-- the deployed app only ever loads these files, it never re-embeds
the corpus itself. Run once per model key in services.semantic_search
.MODEL_CONFIGS -- each model's corpus lives under its own directory,
since embeddings from different models aren't comparable and so can't
share one file.

Stored as float16, not float32 -- halves the file size (~43MB vs
~86MB for 55,745 journals x 384 dims) with no meaningful precision
loss for cosine-similarity ranking (normalized embedding components
are small values well within float16's usable range); cast back to
float32 at load time for the actual dot product.

Prerequisite: models/bge-small-en-v1.5-onnx/data/openalex_topics_full.json
must already exist (benchmark/scripts/fetch_openalex_topics.py against
all_journal_ids.json) -- this script does not fetch it itself, since
that's a slow network-bound step independent of the fast CPU-bound
embedding step here, and re-running this script (e.g. after a DB
content update, or for a second model) shouldn't force a redundant
OpenAlex re-fetch. Reused as-is for every model, not per-model --
OpenAlex topics are a property of the JOURNAL, not of which embedding
model is reading them.

Run from the project root:
    python3 -m scripts.build_semantic_index --model en
    python3 -m scripts.build_semantic_index --model multilingual
"""

import argparse
import json
from pathlib import Path

import numpy as np

from benchmark.baselines.tfidf import build_journal_corpus
from services.repository import get_connection
from services.semantic_search import embed, MODEL_CONFIGS

OPENALEX_TOPICS_PATH = (
    Path(__file__).resolve().parent.parent / "models" / "bge-small-en-v1.5-onnx" / "data" / "openalex_topics_full.json"
)

MAX_CHARS = 400  # same cap used throughout benchmark/ -- keeps worst-case
                  # batch memory bounded regardless of what's in the DB
BATCH_SIZE = 64


def _build_combined_text(baseline_corpus, topics_cache):
    """
    UPGRADE PATH: once journals have a real curated index-terms field
    (#73/#74 -- no such column/table exists yet as of this writing),
    that text should take OpenAlex topics' place here -- either
    replacing it outright or concatenating alongside it, the same way
    this already concatenates baseline text with the OpenAlex proxy.
    Re-run this script for every model key once that data exists; the
    rest of the pipeline (services/semantic_search.py, the /search/semantic
    route) needs no changes either way, since it only ever consumes
    the resulting corpus_embeddings.f16.npy / corpus_ids.json output.
    """
    combined, matched = {}, 0
    for jid, base_text in baseline_corpus.items():
        topics = topics_cache.get(str(jid))
        if topics:
            matched += 1
            combined[jid] = f"{base_text} {' '.join(topics)}"
        else:
            combined[jid] = base_text
    print(f"combined corpus: {matched}/{len(baseline_corpus)} journals used real OpenAlex topics")
    return combined


def run(model_key):
    if model_key not in MODEL_CONFIGS:
        raise SystemExit(f"Unknown model key {model_key!r} -- choices are {list(MODEL_CONFIGS)}")
    if not OPENALEX_TOPICS_PATH.exists():
        raise SystemExit(
            f"{OPENALEX_TOPICS_PATH} not found -- run "
            f"benchmark.scripts.fetch_openalex_topics against all_journal_ids.json first."
        )

    data_dir = MODEL_CONFIGS[model_key]["dir"] / "data"
    corpus_embeddings_path = data_dir / "corpus_embeddings.f16.npy"
    corpus_ids_path = data_dir / "corpus_ids.json"

    conn = get_connection()
    baseline_corpus = build_journal_corpus(conn)
    conn.close()
    print(f"Loaded baseline text for {len(baseline_corpus)} journals", flush=True)

    with open(OPENALEX_TOPICS_PATH) as f:
        topics_cache = json.load(f)

    combined = _build_combined_text(baseline_corpus, topics_cache)
    journal_ids = list(combined.keys())
    texts = [combined[jid][:MAX_CHARS] for jid in journal_ids]

    print(f"Embedding {len(texts)} journal documents with model={model_key!r} ...", flush=True)
    all_embeddings = []
    for start in range(0, len(texts), BATCH_SIZE):
        chunk = texts[start:start + BATCH_SIZE]
        all_embeddings.append(embed(chunk, model_key))
        if start % 5000 < BATCH_SIZE:
            print(f"  embedded {min(start + BATCH_SIZE, len(texts))}/{len(texts)}", flush=True)

    embeddings = np.vstack(all_embeddings).astype(np.float16)

    data_dir.mkdir(parents=True, exist_ok=True)
    np.save(corpus_embeddings_path, embeddings)
    with open(corpus_ids_path, "w") as f:
        json.dump(journal_ids, f)

    print(f"Saved {embeddings.shape} embeddings -> {corpus_embeddings_path}")
    print(f"Saved {len(journal_ids)} journal IDs -> {corpus_ids_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=list(MODEL_CONFIGS))
    args = parser.parse_args()
    run(args.model)


if __name__ == "__main__":
    main()
