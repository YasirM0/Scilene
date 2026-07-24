"""
SINTA importer.

Data source: user-collected export from Indonesia's Science and
Technology Index (https://sinta.kemdikbud.go.id/journals). SINTA
doesn't publish a ready-made bulk export — this pipeline expects a CSV
the user maintains themselves (via their own scraping script), so
please keep that provenance in mind if this data is ever shared beyond
this project.

Matches rows against the existing `journals` table by ISSN (p_issn /
e_issn), falling back to exact normalized title. A match is tagged
"SINTA" with its accreditation tier. No match becomes a new journal row.
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, insert_minimal_journal, tag_source
from utils.issn import normalize_issn


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def import_sinta(csv_path, source_label="SINTA", index=None, conn=None):

    df = pd.read_csv(csv_path, encoding="utf-8")

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

        issns = [
            issn for issn in (
                normalize_issn(row.get("p_issn")),
                normalize_issn(row.get("e_issn")),
            )
            if issn
        ]
        title = _clean(row.get("name"))
        country = "Indonesia"  # SINTA only covers Indonesian journals

        if not issns:
            missing_issn += 1

        journal_id, match_type = index.find(issns, title, country=country)

        # e.g. "S2Accredited" -> "SINTA 2"
        raw_accreditation = _clean(row.get("accreditation"))
        accreditation = None
        if raw_accreditation and raw_accreditation.startswith("S") and "Accredited" in raw_accreditation:
            level = raw_accreditation.replace("Accredited", "").replace("S", "", 1)
            if level.isdigit():
                accreditation = f"SINTA {level}"

        metadata = {"accreditation": accreditation}

        if journal_id is None:
            journal_id = insert_minimal_journal(
                conn,
                title=title,
                publisher=_clean(row.get("publisher")),
                country=country,
                website=_clean(row.get("website")),
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