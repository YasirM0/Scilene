"""
Builds the semantic search corpus embeddings (#143 follow-up, #73/#74
index-terms follow-up) via services/semantic_search.py. Corpus text is
real curated index terms (journals.index_terms, #73/#74) alone -- per
the maintainer's own benchmark, concatenating scope/description text
alongside terms actively hurt retrieval quality. Falls back to
baseline (title+subjects+keywords) text only for journals real index
terms don't cover yet (see scripts/backfill_index_terms.py -- an
ongoing enrichment effort, not a permanent gap).

One model only (sentence-transformers/all-MiniLM-L12-v2) -- an earlier
version of this script also built a second corpus for a multilingual
model handling Arabic/Indonesian queries directly; that whole approach
was removed once real index terms made a translate-to-English +
single-model design clearly better (see
docs/experiments/embedding_benchmarks.md and
services/query_translator.py). Non-English queries are handled before
they ever reach services/semantic_search.py now, so there's only ever
one corpus to build.

One-time (or run-after-a-database-rebuild) offline step. Output is
committed directly to the repo (models/all-MiniLM-L12-v2-onnx/data/),
same convention as data/journal_intelligence.db -- the deployed app
only ever loads these files, it never re-embeds the corpus itself.

SECURITY: this script WIPES journals.index_terms back to NULL in the
database once it's done embedding it. The maintainer's curated index
terms represent real, significant effort and are deliberately kept
off GitHub entirely (data/processed/*_complete.csv never leaves
Cloudcube -- see scripts/fetch_source_csvs.py). But
data/journal_intelligence.db itself IS committed directly to a public
repo, same as every other model/data file this project ships -- so if
index_terms stayed populated in that file, the full curated list would
ship in plain, readable text to anyone who clones the repo, completely
defeating the point of keeping the source CSVs private. The live app
never reads journals.index_terms at request time (only the embeddings
below), and nothing in web/templates/ ever displays it, so wiping it
here costs the shipped app nothing -- only a future rebuild needs it
repopulated first, via scripts/backfill_index_terms.py against the
CSVs, which is the durable, private source of truth this was always
supposed to be.

Stored as float16, not float32 -- halves the file size (~43MB vs
~86MB for 55,745 journals x 384 dims) with no meaningful precision
loss for cosine-similarity ranking (normalized embedding components
are small values well within float16's usable range); cast back to
float32 at load time for the actual dot product.

Run from the project root:
    python3 -m scripts.build_semantic_index
"""

import json

import numpy as np

from benchmark.baselines.tfidf import build_journal_corpus
from services.repository import get_connection
from services.semantic_search import embed, MODEL_DIR

DATA_DIR = MODEL_DIR / "data"
CORPUS_EMBEDDINGS_PATH = DATA_DIR / "corpus_embeddings.f16.npy"
CORPUS_IDS_PATH = DATA_DIR / "corpus_ids.json"

MAX_CHARS = 400  # same cap used throughout benchmark/ -- keeps worst-case
                  # batch memory bounded regardless of what's in the DB
BATCH_SIZE = 64


def _build_index_terms_corpus(conn, baseline_corpus):
    """Real curated index terms alone (comma-joined; the source data
    is semicolon-separated, but a natural comma-separated list reads
    closer to the plain-language text this model was trained on than
    raw semicolons). Falls back to baseline text for journals not yet
    covered by data/processed/*_complete.csv."""
    rows = conn.execute("SELECT id, index_terms FROM journals").fetchall()
    terms_by_id = {jid: terms for jid, terms in rows if terms}

    corpus, matched = {}, 0
    for jid, base_text in baseline_corpus.items():
        terms = terms_by_id.get(jid)
        if terms:
            matched += 1
            corpus[jid] = ", ".join(t.strip() for t in terms.split(";") if t.strip())
        else:
            corpus[jid] = base_text
    print(f"index_terms corpus: {matched}/{len(baseline_corpus)} journals used real curated index "
          f"terms ({len(baseline_corpus) - matched} fell back to baseline text)")
    return corpus


def run():
    conn = get_connection()
    baseline_corpus = build_journal_corpus(conn)
    combined = _build_index_terms_corpus(conn, baseline_corpus)
    print(f"Loaded baseline text for {len(baseline_corpus)} journals", flush=True)

    journal_ids = list(combined.keys())
    texts = [combined[jid][:MAX_CHARS] for jid in journal_ids]

    print(f"Embedding {len(texts)} journal documents ...", flush=True)
    all_embeddings = []
    for start in range(0, len(texts), BATCH_SIZE):
        chunk = texts[start:start + BATCH_SIZE]
        all_embeddings.append(embed(chunk))
        if start % 5000 < BATCH_SIZE:
            print(f"  embedded {min(start + BATCH_SIZE, len(texts))}/{len(texts)}", flush=True)

    embeddings = np.vstack(all_embeddings).astype(np.float16)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CORPUS_EMBEDDINGS_PATH, embeddings)
    with open(CORPUS_IDS_PATH, "w") as f:
        json.dump(journal_ids, f)

    print(f"Saved {embeddings.shape} embeddings -> {CORPUS_EMBEDDINGS_PATH}")
    print(f"Saved {len(journal_ids)} journal IDs -> {CORPUS_IDS_PATH}")

    # See module docstring's SECURITY note -- embeddings are already
    # safely on disk above, so wiping the source text here costs
    # nothing the shipped app needs, and keeps it out of the database
    # file that gets committed to a public repo.
    stripped = conn.execute(
        "SELECT COUNT(*) FROM journals WHERE index_terms IS NOT NULL AND index_terms != ''"
    ).fetchone()[0]
    conn.execute("UPDATE journals SET index_terms = NULL")
    conn.commit()
    conn.close()
    print(f"Wiped index_terms back to NULL for {stripped} journals (embeddings already saved above -- "
          f"see module docstring's SECURITY note).")


if __name__ == "__main__":
    run()
