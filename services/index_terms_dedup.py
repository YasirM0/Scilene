"""
Embedding-based deduplication for curated index terms (#121).

Complements services.repository.update_index_terms()'s existing
case-insensitive EXACT-match dedup with a second pass that catches
semantically-equivalent-but-differently-worded terms -- "Machine
Learning" vs "ML" vs "Machine Learning Techniques" -- which simple
string matching can never catch. Runs once, at backfill time, as the
final step of scripts/backfill_index_terms.py, never at search
request time -- a completely separate concern from
services/semantic_search.py's own embed(), even though it reuses that
same function.

Deliberately NOT wired into update_index_terms() itself: that would
make services/repository.py (imported by nearly every importer and
route in this app) depend on services/semantic_search.py, which
itself imports FROM services/repository.py -- a circular import.
Keeping this as a separate, explicit backfill step avoids that
entirely.

THRESHOLD IS UNVALIDATED against the real curated term lists -- they
live in private, off-GitHub CSVs (see scripts/fetch_source_csvs.py)
that aren't present in every environment this code runs in.
DEDUP_SIMILARITY_THRESHOLD=0.90 is a conservative starting point
(near-exact paraphrase territory for all-MiniLM-L12-v2, not just "a
related topic"), but the maintainer should spot-check a real backfill
run's before/after term lists -- same spot-check discipline the
original generation pipeline already used for quality gating -- before
trusting a lower threshold or considering #121 fully closed.
"""

import numpy as np

from services.semantic_search import embed

DEDUP_SIMILARITY_THRESHOLD = 0.90

# services.semantic_search.embed() already batches its own ONNX calls
# internally -- this just caps how many terms go into one such call at
# a time, so memory stays bounded regardless of how many journals have
# index_terms.
EMBED_BATCH_SIZE = 512


def _dedup_one_journal(terms, vectors, threshold):
    """
    Greedily keeps the FIRST occurrence of each semantic cluster (the
    earliest source's own phrasing) and drops any later term whose
    cosine similarity to an already-kept term meets `threshold`.
    O(n^2) comparisons -- fine for one journal's term list (tens of
    terms), not meant to run across journals.
    """
    kept_terms, kept_vectors = [], []
    for term, vector in zip(terms, vectors):
        is_duplicate = any(float(vector @ kv) >= threshold for kv in kept_vectors)
        if not is_duplicate:
            kept_terms.append(term)
            kept_vectors.append(vector)
    return kept_terms


def run_embedding_dedup(conn, threshold=DEDUP_SIMILARITY_THRESHOLD):
    """
    Final backfill-time pass (#121) over every journal with
    index_terms: merges semantically-equivalent terms WITHIN each
    journal's own list. Embeds every term across every journal in
    large shared batches rather than one embed() call per journal
    (per-call overhead would otherwise dominate over ~20-50k
    journals); the actual clustering/dropping is still done per
    journal -- merging the same term across two DIFFERENT journals
    would be wrong, they're independent lists, not one shared
    vocabulary.

    Returns (journals_changed, terms_dropped) for the caller to report.
    """
    rows = conn.execute(
        "SELECT id, index_terms FROM journals WHERE index_terms IS NOT NULL AND index_terms != ''"
    ).fetchall()

    all_terms = []
    spans = []  # (journal_id, start, end) slices into all_terms / vectors
    for journal_id, raw in rows:
        terms = [t.strip() for t in raw.split(";") if t.strip()]
        start = len(all_terms)
        all_terms.extend(terms)
        spans.append((journal_id, start, len(all_terms)))

    if not all_terms:
        return 0, 0

    batches = []
    for start in range(0, len(all_terms), EMBED_BATCH_SIZE):
        batches.append(embed(all_terms[start:start + EMBED_BATCH_SIZE]))
    vectors = np.vstack(batches)

    journals_changed = 0
    terms_dropped = 0
    for journal_id, start, end in spans:
        terms = all_terms[start:end]
        if len(terms) < 2:
            continue  # nothing to dedup within a single-term list

        kept = _dedup_one_journal(terms, vectors[start:end], threshold)
        if len(kept) != len(terms):
            terms_dropped += len(terms) - len(kept)
            journals_changed += 1
            conn.execute(
                "UPDATE journals SET index_terms = ? WHERE id = ?",
                ("; ".join(kept), journal_id),
            )

    return journals_changed, terms_dropped
