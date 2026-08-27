"""
Backfills journals.index_terms (#73/#74) onto the EXISTING journal
catalog by matching data/processed/*_complete.csv rows against
already-imported journals -- never creates a new row, never touches
any other field. Purely additive.

Why a separate pass instead of just re-running scripts/build_database.py
against the complete files: the complete files currently cover a
SUBSET of the full catalog (e.g. doaj_complete.csv has ~22,000 rows vs.
the ~55,745-journal full database), and DOAJImporter in particular
always INSERTS new rows rather than matching -- running it against a
second, smaller file would create duplicate journals, not backfill the
originals. This script only ever calls update_index_terms() (a
COALESCE-based UPDATE, never an INSERT), using the exact same
ISSN/title matching (services.dedup.JournalIndex) every importer
already uses, so it's safe to run against the full, already-built
database regardless of which subset of journals the complete files
happen to cover.

Run from the project root, after the database is already built:
    python -m scripts.backfill_index_terms

Full rebuild cycle, every time (SECURITY -- see
scripts/build_semantic_index.py's own docstring): this script
populates journals.index_terms from the private, off-GitHub CSVs,
but scripts/build_semantic_index.py WIPES that column back to NULL
immediately after it finishes building embeddings from it, so the
committed data/journal_intelligence.db never carries the maintainer's
curated term list in plain text to a public repo. That means this
script needs to be re-run before every corpus rebuild, not just once
ever -- the database's own copy of index_terms is intentionally
transient, not a persistent store.
    python -m scripts.fetch_source_csvs      # pull the 3 CSVs from Cloudcube
    python -m scripts.backfill_index_terms   # populate journals.index_terms (this script)
    python -m scripts.build_semantic_index   # embed it, then wipe it back to NULL
"""

from pathlib import Path

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, update_index_terms
from utils.issn import extract_issns, normalize_issn

ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED = ROOT / "data" / "processed"


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def _backfill_doaj(index, conn):
    df = pd.read_csv(DATA_PROCESSED / "doaj_complete.csv", dtype=str)
    matched = unmatched = 0
    for _, row in df.iterrows():
        issns = [
            issn for issn in (
                normalize_issn(row.get("Journal ISSN (print version)")),
                normalize_issn(row.get("Journal EISSN (online version)")),
            )
            if issn
        ]
        title = _clean(row.get("Journal title"))
        journal_id, _ = index.find(issns, title, country=_clean(row.get("Country of publisher")))
        if journal_id is None:
            unmatched += 1
            continue
        update_index_terms(conn, journal_id, _clean(row.get("index_terms")))
        matched += 1
    return matched, unmatched


def _backfill_scimago(index, conn):
    df = pd.read_csv(DATA_PROCESSED / "scimago_complete.csv", dtype=str)
    matched = unmatched = 0
    for _, row in df.iterrows():
        issns = extract_issns(row.get("Issn"))
        title = _clean(row.get("Title"))
        country = _clean(row.get("Country"))
        journal_id, _ = index.find(issns, title, country=country)
        if journal_id is None:
            unmatched += 1
            continue
        update_index_terms(conn, journal_id, _clean(row.get("index_terms")))
        matched += 1
    return matched, unmatched


def _backfill_sinta(index, conn):
    df = pd.read_csv(DATA_PROCESSED / "sinta_complete.csv", dtype=str)
    matched = unmatched = 0
    for _, row in df.iterrows():
        issns = [
            issn for issn in (
                normalize_issn(row.get("p_issn")),
                normalize_issn(row.get("e_issn")),
            )
            if issn
        ]
        title = _clean(row.get("name"))
        journal_id, _ = index.find(issns, title, country="Indonesia")
        if journal_id is None:
            unmatched += 1
            continue
        update_index_terms(conn, journal_id, _clean(row.get("index_terms")))
        matched += 1
    return matched, unmatched


def run():
    conn = get_connection()
    index = JournalIndex(conn)

    for label, fn in [("DOAJ", _backfill_doaj), ("Scopus/SCImago", _backfill_scimago), ("SINTA", _backfill_sinta)]:
        matched, unmatched = fn(index, conn)
        conn.commit()
        print(f"{label:16} matched: {matched:6}  unmatched (no existing journal found): {unmatched:6}")

    total = conn.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
    with_terms = conn.execute(
        "SELECT COUNT(*) FROM journals WHERE index_terms IS NOT NULL AND index_terms != ''"
    ).fetchone()[0]
    conn.close()

    print()
    print(f"Total journals: {total}")
    print(f"With index_terms: {with_terms} ({with_terms / total * 100:.1f}%)")


if __name__ == "__main__":
    run()
