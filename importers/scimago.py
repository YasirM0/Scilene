"""
SCImago Journal Rank importer — used for both Scopus and Web of Science.

Data source: SCImago Journal & Country Rank (https://www.scimagojr.com).
SCImago's data is provided for informational/non-commercial use.
Attribution kept wherever this data is shown or redistributed:
"Data source: SCImago Journal & Country Rank (www.scimagojr.com)."

Two files in this project share this exact format:
  - data/processed/scimago_complete.csv  -> full SCImago export (plus
                                      appended scope/index_terms columns
                                      this importer doesn't read), tagged
                                      "Scopus"
  - data/enrichment/wos.csv       -> the same export, pre-filtered by the
                                      user to Web-of-Science-indexed
                                      journals only, tagged "Web of Science"
                                      (lives in data/enrichment/, not
                                      data/processed/, since it's derived
                                      from scimagojr.csv rather than an
                                      independent primary-source export,
                                      and small enough to stay committed)

Each row is matched against the existing `journals` table by ISSN, then
by exact normalized title (see services.dedup). A match gets tagged
with this source plus its quartile/SJR/H-index. No match becomes a new
journal row, tagged only with this source — this does not fabricate a
DOAJ presence or any other metadata for it.

Also tags the "Open Access Diamond" column (#98) as display-only
metadata enrichment (journal_enrichment, not a journals/journal_sources
column) — the issue frames Diamond OA as enabling "future filtering",
which isn't implemented yet; promoting it to a real filterable column
is separate work. Since a Diamond OA journal is by definition also
Open Access, and this importer runs for both Scopus and WoS (the same
underlying SCImago row, just pre-filtered), tagging happens at most
once per journal regardless of which pass(es) match it.
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, insert_minimal_journal, tag_source, tag_enrichment, update_index_terms
from utils.issn import extract_issns


def _parse_decimal(raw):
    """SCImago uses comma as the decimal separator (e.g. '104,065')."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def import_scimago(csv_path, source_label, index=None, conn=None, sep=";"):
    """
    `sep` defaults to ";" (data/enrichment/wos.csv's own raw-SCImago-export
    format), but data/processed/scimago_complete.csv -- the enriched
    Scopus source, see scripts/build_database.py -- is comma-separated
    instead, so that call passes sep="," explicitly.
    """

    df = pd.read_csv(csv_path, sep=sep, encoding="utf-8")

    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    if index is None:
        index = JournalIndex(conn)

    matched_by_issn = 0
    matched_by_title = 0
    created = 0
    missing_issn = 0
    diamond_tagged = 0
    duplicate_rows_skipped = 0

    # Same defensive dedup as importers/sinta.py -- SCImago's own
    # "Sourceid" is its stable per-journal identifier. Currently
    # near-zero duplication in practice, but this keeps the import
    # self-checking (see the assertion below) if a future export ever
    # isn't as clean, instead of silently under- or over-counting with
    # no visible signal.
    seen_source_ids = set()

    for _, row in df.iterrows():

        source_id = _clean(row.get("Sourceid"))
        if source_id is not None:
            if source_id in seen_source_ids:
                duplicate_rows_skipped += 1
                continue
            seen_source_ids.add(source_id)

        issns = extract_issns(row.get("Issn"))
        title = _clean(row.get("Title"))
        country = _clean(row.get("Country"))

        if not issns:
            missing_issn += 1

        journal_id, match_type = index.find(issns, title, country=country)

        metadata = {
            "quartile": _clean(row.get("SJR Best Quartile")),
            "sjr": _parse_decimal(row.get("SJR")),
            "h_index": int(row["H index"]) if pd.notna(row.get("H index")) else None,
        }

        if journal_id is None:
            journal_id = insert_minimal_journal(
                conn,
                title=title,
                publisher=_clean(row.get("Publisher")),
                country=country,
                issn_print=issns[0] if issns else None,
                issn_online=issns[1] if len(issns) > 1 else None,
                source=source_label,
            )
            index.add(journal_id, issns, title, country=country)
            created += 1
        elif match_type == "issn":
            matched_by_issn += 1
        else:
            matched_by_title += 1

        tag_source(conn, journal_id, source_label, metadata)
        update_index_terms(conn, journal_id, _clean(row.get("index_terms")))

        if _clean(row.get("Open Access Diamond")) == "Yes":
            tag_enrichment(conn, journal_id, "diamond_oa", {})
            diamond_tagged += 1

    if owns_connection:
        conn.commit()
        conn.close()

    summary = {
        "source": source_label,
        "rows": len(df),
        "duplicate_rows_skipped": duplicate_rows_skipped,
        "matched_by_issn": matched_by_issn,
        "matched_by_title": matched_by_title,
        "created": created,
        "missing_issn": missing_issn,
        "diamond_tagged": diamond_tagged,
    }

    distinct_journals = matched_by_issn + matched_by_title + created
    assert duplicate_rows_skipped + distinct_journals == len(df), (
        f"{source_label} import row accounting doesn't add up: "
        f"{duplicate_rows_skipped} duplicates + {distinct_journals} processed "
        f"!= {len(df)} total rows"
    )

    print(
        f"{source_label}: {len(df)} rows ({duplicate_rows_skipped} duplicate listings skipped -> "
        f"{distinct_journals} distinct journals) | matched by ISSN: {matched_by_issn} | "
        f"matched by title: {matched_by_title} | new journals created: {created} | "
        f"rows with no usable ISSN: {missing_issn} | Diamond OA: {diamond_tagged}"
    )

    return index, summary