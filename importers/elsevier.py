"""
Elsevier Scopus Source List importer (#98).

SCImago (importers/scimago.py) is a periodic ranking snapshot: it's
authoritative for quartile/SJR/H-index, but a journal can be added to
Scopus (or drop off it) between SCImago snapshots. The Elsevier Source
List is Elsevier's own, more current list of what's actually Scopus-
indexed right now -- this importer uses it to catch Scopus-indexed
journals SCImago hasn't caught up to yet, WITHOUT touching the
quartile/SJR/H-index that SCImago already provided (see
services.repository.tag_source's COALESCE upsert for how that's kept
safe even though both importers write to the same journal_sources row).

Every matched row (Active or Inactive) is tagged, with:
  - active: 1/0, from Elsevier's "Active or Inactive" column. Journals
    with active=0 are hidden from default search results and only
    surfaced via the existing "Show weaker recommendations" toggle
    (web/search_presentation.py's filter_visible_results) -- no
    separate filter, per the issue.
  - coverage: e.g. "1998-2019", shown on the journal card only when
    active=0 (a still-Active journal's coverage is just "ongoing",
    not informative).
  - source_record_id: Elsevier's own Scopus identifier. Matched FIRST
    on a re-run (via `_by_source_record_id`, built from what a prior
    run already stored) before falling back to ISSN/title -- this is
    what makes an annual re-import idempotent and immune to a journal
    having changed its title or ISSN between Elsevier snapshots.
  - article_language: stored for future language filtering (#89
    filters on `journals.languages`, which is DOAJ's field --
    Elsevier's per-source article language is intentionally NOT wired
    into that filter here, just preserved for later).

Also writes journals.publication_type (#128) from Elsevier's own
"Source Type" column (currently only ever "Journal", "Book Series", or
"Trade Journal" in the real dataset) -- a journal-level attribute, not
per-source, so it's a plain UPDATE via
services.repository.update_publication_type, not part of the
journal_sources upsert above.

Runs AFTER importers/scimago.py in scripts/build_database.py.
  - Matched to an existing journal: tagged Scopus (if not already) and
    given whatever Elsevier-only fields it has, without touching a
    quartile/sjr/h_index SCImago already set.
  - Not matched to any existing journal: skipped. This importer never
    creates a new journal row -- Elsevier-only journals not in DOAJ,
    Scopus/SCImago, or SINTA are out of scope for this pass (see #101
    for expanding coverage beyond currently indexed datasets).

Not implemented (out of scope for this pass, see docs/DATABASE.md):
ASJC codes, top-level disciplines, reordering the import pipeline to
put Elsevier first. Title history / related titles are handled
separately by importers/aliases.py (#100).
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, tag_source, update_publication_type
from utils.issn import extract_issns


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def _load_by_source_record_id(conn, source_label):
    rows = conn.execute(
        "SELECT source_record_id, journal_id FROM journal_sources "
        "WHERE source = ? AND source_record_id IS NOT NULL",
        (source_label,),
    ).fetchall()
    return {record_id: journal_id for record_id, journal_id in rows}


def _find_added_to_list_column(columns):
    """
    Elsevier bakes the snapshot's own vintage into the column header
    itself (e.g. "Added to List June 2026") rather than a per-row
    date -- there's no separate date field to read. Finding the column
    by prefix (not a hardcoded name) means a future CSV with a
    different month/year still gets picked up without a code change.
    """
    for column in columns:
        if column.startswith("Added to List "):
            return column
    return None


def import_elsevier(csv_path, source_label="Scopus", index=None, conn=None):

    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
    added_to_list_column = _find_added_to_list_column(df.columns)
    added_to_list_period = (
        added_to_list_column[len("Added to List "):] if added_to_list_column else None
    )

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

    by_source_record_id = _load_by_source_record_id(conn, source_label)

    newly_tagged = 0
    already_tagged = 0
    active_count = 0
    inactive_count = 0
    no_match = 0

    for _, row in df.iterrows():

        source_record_id = _clean(row.get("Sourcerecord ID"))
        issns = extract_issns(row.get("ISSN")) + extract_issns(row.get("EISSN"))
        title = _clean(row.get("Source Title"))

        journal_id = by_source_record_id.get(source_record_id) if source_record_id else None
        if journal_id is None:
            journal_id, _match_type = index.find(issns, title, country=None)

        if journal_id is None:
            no_match += 1
            continue

        is_active = _clean(row.get("Active or Inactive")) == "Active"
        if is_active:
            active_count += 1
        else:
            inactive_count += 1

        # "Added" this snapshot -> store the period as plain text
        # ("June 2026"), not a relative phrase that goes stale --
        # #98 explicitly warns against "Recently indexed" for exactly
        # that reason. NaN/missing -> None, same as every other field.
        added_to_list = None
        if added_to_list_column and _clean(row.get(added_to_list_column)) == "Added":
            added_to_list = added_to_list_period

        # No quartile/sjr/h_index passed here -- Scopus-indexed per
        # Elsevier, but that's SCImago's field to set (or leave
        # unavailable), tag_source's COALESCE upsert never lets this
        # call touch it.
        tag_source(conn, journal_id, source_label, metadata={
            "active": is_active,
            "coverage": _clean(row.get("Coverage")),
            "source_record_id": source_record_id,
            "article_language": _clean(
                row.get("Article Language in Source (Three-Letter ISO Language Codes)")
            ),
            "added_to_list": added_to_list,
        })

        update_publication_type(conn, journal_id, _clean(row.get("Source Type")))

        if journal_id in already_scopus:
            already_tagged += 1
        else:
            already_scopus.add(journal_id)
            newly_tagged += 1

        if source_record_id:
            by_source_record_id[source_record_id] = journal_id

    if owns_connection:
        conn.commit()
        conn.close()

    summary = {
        "source": source_label,
        "rows": len(df),
        "newly_tagged": newly_tagged,
        "already_tagged": already_tagged,
        "active": active_count,
        "inactive": inactive_count,
        "no_match": no_match,
    }

    print(
        f"{source_label} (Elsevier): {len(df)} rows | newly tagged Scopus (no SCImago rank yet): "
        f"{newly_tagged} | already Scopus via SCImago: {already_tagged} | "
        f"active: {active_count} | inactive: {inactive_count} | no match in database: {no_match}"
    )

    return index, summary
