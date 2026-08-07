"""
Elsevier Scopus Source List importer (#98).

SCImago (importers/scimago.py) is a periodic ranking snapshot: it's
authoritative for quartile/SJR/H-index, but a journal can be added to
Scopus (or drop off it) between SCImago snapshots. The Elsevier Source
List is Elsevier's own, more current list of what's actually Scopus-
indexed right now -- this importer uses it to catch Scopus-indexed
journals SCImago hasn't caught up to yet, WITHOUT touching the
quartile/SJR/H-index that SCImago already provided.

Only "Active" rows are considered (issue: "Active journals remain the
default search results" -- Inactive handling, coverage display, title
history, ASJC taxonomy, and article language from the same issue are
NOT implemented here, see docs/DATABASE.md).

Runs AFTER importers/scimago.py in scripts/build_database.py, and only
ever fills a gap:
  - Matched to an existing journal, not yet tagged "Scopus" (e.g. only
    in DOAJ/SINTA so far, or genuinely missing from SCImago's
    snapshot): tags it "Scopus" with quartile/sjr/h_index left
    unavailable (None) rather than inventing a rank.
  - Matched to a journal ALREADY tagged "Scopus" (via SCImago): left
    untouched. Re-tagging here would overwrite its real quartile/sjr
    with None, which is exactly the bug this importer must not cause.
  - Not matched to any existing journal: skipped. This importer never
    creates a new journal row -- Elsevier-only journals not in DOAJ,
    Scopus/SCImago, or SINTA are out of scope for this pass (see #101
    for expanding coverage beyond currently indexed datasets).
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, tag_source
from utils.issn import extract_issns


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def import_elsevier(csv_path, source_label="Scopus", index=None, conn=None):

    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)

    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    if index is None:
        index = JournalIndex(conn)

    already_scopus = {
        journal_id
        for (journal_id,) in conn.execute(
            "SELECT journal_id FROM journal_sources WHERE source = ?", (source_label,)
        ).fetchall()
    }

    newly_tagged = 0
    already_tagged = 0
    inactive_skipped = 0
    no_match = 0

    for _, row in df.iterrows():

        if _clean(row.get("Active or Inactive")) != "Active":
            inactive_skipped += 1
            continue

        issns = extract_issns(row.get("ISSN")) + extract_issns(row.get("EISSN"))
        title = _clean(row.get("Source Title"))
        publisher = _clean(row.get("Publisher"))

        journal_id, _match_type = index.find(issns, title, country=None)

        if journal_id is None:
            no_match += 1
            continue

        if journal_id in already_scopus:
            already_tagged += 1
            continue

        # No quartile/sjr/h_index -- Scopus-indexed per Elsevier, but
        # SCImago hasn't ranked it (yet, or ever). Represented as
        # "Quartile unavailable" downstream, not missing/invalid data.
        tag_source(conn, journal_id, source_label, metadata={})
        already_scopus.add(journal_id)
        newly_tagged += 1

    if owns_connection:
        conn.commit()
        conn.close()

    summary = {
        "source": source_label,
        "rows": len(df),
        "newly_tagged": newly_tagged,
        "already_tagged": already_tagged,
        "inactive_skipped": inactive_skipped,
        "no_match": no_match,
    }

    print(
        f"{source_label} (Elsevier): {len(df)} rows | newly tagged Scopus (no SCImago rank yet): "
        f"{newly_tagged} | already Scopus via SCImago: {already_tagged} | "
        f"inactive (skipped): {inactive_skipped} | no match in database: {no_match}"
    )

    return index, summary
