"""
Journal Alias & Historical Title System (#100).

Imports alternate/historical titles for journals that already exist in
the database -- translated titles (DOAJ), former/continued/related
titles (Elsevier), and original/English titles (ERIH PLUS). Matched by
ISSN against `index` (the same services.dedup.JournalIndex the base
importers already built), exactly like importers/elsevier.py and the
enrichment providers: a row that can't be matched to an existing
journal is skipped, never used to create a new one.

Deliberately narrow, per docs/DATABASE.md's scoping convention (see
#98's Elsevier importer for precedent):
  - Only the three sources the issue names (DOAJ, Elsevier, ERIH PLUS)
    are wired up. Adding a fourth source (ROAD, Crossref, OpenAlex,
    Wikidata, ...) is a new function here, not a schema or matching
    change -- see insert_alias()/journal_aliases in data/schema.sql.
  - Runs AFTER all base imports (scripts/build_database.py), so it can
    reuse the fully-populated `index` rather than re-deriving matches.
  - Does NOT wire aliases into the CSV-import matching pass itself
    (i.e. importers/scimago.py, importers/sinta.py, importers/
    elsevier.py still match by ISSN/title only) -- alias-as-fallback
    matching (services/dedup.py JournalIndex.find()) only takes effect
    for imports that run AFTER this one. Re-ordering build_database.py
    to run alias import earlier would extend that fallback to more
    importers; left as a future decision, not assumed here.
"""

import pandas as pd

from services.repository import insert_alias
from utils.issn import extract_issns, normalize_issn


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip()
    return value or None


def _same_as_primary(index, journal_id, alias):
    primary = index.title_by_id.get(journal_id)
    return primary is not None and str(primary).strip().lower() == alias.strip().lower()


def _add_alias(conn, index, journal_id, alias, alias_type, source, counters):
    alias = _clean(alias)
    if not alias or _same_as_primary(index, journal_id, alias):
        return
    insert_alias(conn, journal_id, alias, alias_type, source)
    counters["added"] += 1


def import_doaj_aliases(csv_path, index, conn):
    """DOAJ 'Alternative title' -> alias_type 'Alternative title'."""

    df = pd.read_csv(csv_path, dtype=str)
    counters = {"added": 0, "no_match": 0, "no_alias": 0}

    for _, row in df.iterrows():
        alt_title = _clean(row.get("Alternative title"))
        if not alt_title:
            counters["no_alias"] += 1
            continue

        issns = extract_issns(row.get("Journal ISSN (print version)")) + \
            extract_issns(row.get("Journal EISSN (online version)"))
        title = _clean(row.get("Journal title"))
        country = _clean(row.get("Country of publisher"))

        journal_id, _match_type = index.find(issns, title, country=country)
        if journal_id is None:
            counters["no_match"] += 1
            continue

        _add_alias(conn, index, journal_id, alt_title, "Alternative title", "DOAJ", counters)

    print(
        f"DOAJ aliases: {counters['added']} added | "
        f"{counters['no_alias']} rows with no alternative title | "
        f"{counters['no_match']} rows with no matching journal"
    )
    return counters


# A "Related Title 1" only carries a specific relationship type when
# Elsevier's own "Title History Indication" says so (e.g. "Formerly
# known as", "Continued as") -- Related Title 2-4 are always plain
# related titles, Elsevier doesn't classify those further.
_ELSEVIER_HISTORY_TYPES = {
    "Formerly known as",
    "Continued as",
    "Incorporated into",
    "Incorporating",
    "Formerly part of",
    "Formerly included in",
    "See also",
}


def import_elsevier_aliases(csv_path, index, conn):
    """
    Elsevier 'Related Title 1' (typed via 'Title History Indication'
    when it's a recognized relationship, else 'Related title') plus
    'Other Related Title 2/3/4' (always 'Related title').
    """

    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
    counters = {"added": 0, "no_match": 0}

    for _, row in df.iterrows():
        issns = extract_issns(row.get("ISSN")) + extract_issns(row.get("EISSN"))
        title = _clean(row.get("Source Title"))

        related_1 = _clean(row.get("Related Title 1"))
        related_2 = _clean(row.get("Other Related Title 2"))
        related_3 = _clean(row.get("Other Related Title 3"))
        related_4 = _clean(row.get("Other Related Title 4"))

        if not any((related_1, related_2, related_3, related_4)):
            continue

        journal_id, _match_type = index.find(issns, title, country=None)
        if journal_id is None:
            counters["no_match"] += 1
            continue

        history = _clean(row.get("Title History Indication"))
        related_1_type = history if history in _ELSEVIER_HISTORY_TYPES else "Related title"

        for alias, alias_type in (
            (related_1, related_1_type),
            (related_2, "Related title"),
            (related_3, "Related title"),
            (related_4, "Related title"),
        ):
            if alias:
                _add_alias(conn, index, journal_id, alias, alias_type, "Elsevier", counters)

    print(
        f"Elsevier aliases: {counters['added']} added | "
        f"{counters['no_match']} rows with no matching journal"
    )
    return counters


def import_erihplus_aliases(csv_path, index, conn):
    """ERIH PLUS 'navn' (original title) + 'navn_en' (English title)."""

    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
    counters = {"added": 0, "no_match": 0}

    for _, row in df.iterrows():
        original_title = _clean(row.get("navn"))
        english_title = _clean(row.get("navn_en"))

        if not original_title and not english_title:
            continue

        issns = []
        for column in ("tidsskriftISSNP", "tidsskriftISSNE"):
            issn = normalize_issn(row.get(column))
            if issn:
                issns.append(issn)

        journal_id, _match_type = index.find(issns, english_title or original_title, country=None)
        if journal_id is None:
            counters["no_match"] += 1
            continue

        if original_title:
            _add_alias(conn, index, journal_id, original_title, "Original title", "ERIH PLUS", counters)
        if english_title:
            _add_alias(conn, index, journal_id, english_title, "English title", "ERIH PLUS", counters)

    print(
        f"ERIH PLUS aliases: {counters['added']} added | "
        f"{counters['no_match']} rows with no matching journal"
    )
    return counters
