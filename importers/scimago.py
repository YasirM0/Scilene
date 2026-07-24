"""
SCImago Journal Rank importer — used for both Scopus and Web of Science.

Data source: SCImago Journal & Country Rank (https://www.scimagojr.com).
SCImago's data is provided for informational/non-commercial use.
Attribution kept wherever this data is shown or redistributed:
"Data source: SCImago Journal & Country Rank (www.scimagojr.com)."

Two files in this project share this exact format:
  - data/raw/scimagojr.csv  -> full SCImago export, tagged "Scopus"
  - data/raw/wos.csv        -> the same export, pre-filtered by the user
                                to Web-of-Science-indexed journals only,
                                tagged "Web of Science"

Each row is matched against the existing `journals` table by ISSN, then
by exact normalized title (see services.dedup). A match gets tagged
with this source plus its quartile/SJR/H-index. No match becomes a new
journal row, tagged only with this source — this does not fabricate a
DOAJ presence or any other metadata for it.
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, insert_minimal_journal, tag_source
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


def import_scimago(csv_path, source_label, index=None, conn=None):

    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    if index is None:
        index = JournalIndex(conn)

    matched_by_issn = 0
    matched_by_title = 0
    created = 0
    missing_issn = 0

    for _, row in df.iterrows():

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

    if owns_connection:
        conn.commit()
        conn.close()

    summary = {
        "source": source_label,
        "rows": len(df),
        "matched_by_issn": matched_by_issn,
        "matched_by_title": matched_by_title,
        "created": created,
        "missing_issn": missing_issn,
    }

    print(
        f"{source_label}: {len(df)} rows | matched by ISSN: {matched_by_issn} | "
        f"matched by title: {matched_by_title} | new journals created: {created} | "
        f"rows with no usable ISSN: {missing_issn}"
    )

    return index, summary