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

Also tags Garuda indexing (#97) from the same file's `garuda_indexed`
column, as display-only metadata enrichment (journal_enrichment, not
journal_sources) -- per the issue, "Garuda should be treated as
journal metadata rather than a search filter", i.e. it must never
become filterable or affect ranking, exactly like ROAD/ERIH PLUS/
SciELO/AJOL (docs/ENRICHMENT.md). Garuda's data happens to arrive
bundled in the SINTA file rather than its own, so it's tagged here
rather than as a separate importers/enrichment/ provider.
"""

import pandas as pd

from services.dedup import JournalIndex
from services.repository import get_connection, insert_minimal_journal, tag_source, tag_enrichment, update_index_terms
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
    garuda_tagged = 0
    duplicate_rows_skipped = 0

    # SINTA's own export repeats a journal's row once per listing
    # (observed: once per subject-area classification) rather than
    # once per journal -- `journal_id` is SINTA's own stable
    # identifier for the underlying journal, so seeing it twice in
    # this file means the same journal, not two. Deduplicating on it
    # explicitly (rather than relying on tag_source()'s upsert to
    # silently absorb the repeat) keeps this import's own accounting
    # honest: the assertion below only passes if every row is
    # accounted for as either a skipped duplicate or a processed
    # journal, so swapping in a differently-sized future export
    # self-documents in the printed summary instead of silently
    # changing the imported count with no visible signal.
    seen_source_ids = set()

    for _, row in df.iterrows():

        source_journal_id = _clean(row.get("journal_id"))
        if source_journal_id is not None:
            if source_journal_id in seen_source_ids:
                duplicate_rows_skipped += 1
                continue
            seen_source_ids.add(source_journal_id)

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
        update_index_terms(conn, journal_id, _clean(row.get("index_terms")))

        if bool(row.get("garuda_indexed")):
            tag_enrichment(conn, journal_id, "garuda", {})
            garuda_tagged += 1

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
        "garuda_tagged": garuda_tagged,
    }

    distinct_journals = matched_by_issn + matched_by_title + created
    # Self-checking accounting: every row in the file must land in
    # exactly one bucket. If this ever fails, something about the
    # file's shape changed in a way this importer doesn't understand
    # yet (e.g. a non-identical duplicate journal_id) -- fail loudly
    # rather than silently import a number nobody can explain.
    assert duplicate_rows_skipped + distinct_journals == len(df), (
        f"{source_label} import row accounting doesn't add up: "
        f"{duplicate_rows_skipped} duplicates + {distinct_journals} processed "
        f"!= {len(df)} total rows"
    )

    print(
        f"{source_label}: {len(df)} rows ({duplicate_rows_skipped} duplicate listings skipped -> "
        f"{distinct_journals} distinct journals) | matched by ISSN: {matched_by_issn} | "
        f"matched by title: {matched_by_title} | new journals created: {created} | "
        f"rows with no usable ISSN: {missing_issn} | Garuda-indexed: {garuda_tagged}"
    )

    return index, summary