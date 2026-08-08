"""
Full database build pipeline.

Rebuilds journal_intelligence.db from scratch using the CSV files in
data/raw/:
  - doaj.csv       -> base journal catalog (richest per-journal metadata)
  - scimagojr.csv  -> tags matching journals as Scopus-indexed
                       (+ quartile/SJR/H-index); creates new rows for
                       Scopus-only journals not already in DOAJ
  - wos.csv        -> SCImago's own export, pre-filtered by the user to
                       Web-of-Science-indexed journals only; tags matches
                       as Web-of-Science-indexed
  - sinta.csv      -> tags matching journals as SINTA-indexed
                       (+ accreditation); creates new rows for SINTA-only
                       journals not already present

Then, from data/enrichment/:
  - Elsevier.csv   -> fills Scopus-indexing gaps SCImago's periodic
                       snapshot hasn't caught up to yet (#98) -- tags a
                       matched, Active journal as Scopus-indexed if it
                       isn't already, WITHOUT touching a quartile/sjr/
                       h_index SCImago already set. This one DOES
                       affect the Scopus filter, unlike the enrichment
                       providers below -- see importers/elsevier.py.
  - road.tsv, erihplus.csv, scielo_journals.csv, ajol.csv -> tag
                       journals with display-only metadata
                       (docs/ENRICHMENT.md) that can never affect which
                       journals are found or how they're ranked. A
                       journal an enrichment provider can't match by
                       ISSN is simply skipped, never turned into a new
                       journal row.
  - doaj.csv, Elsevier.csv, erihplus.csv (again) -> alternate/
                       historical titles (#100, journal_aliases) --
                       DOAJ alternative titles, Elsevier former/
                       continued/related titles, ERIH PLUS original &
                       English titles. Matched to an existing journal
                       by ISSN only, same skip-if-unmatched rule as
                       above; see importers/aliases.py.

To update any dataset: replace the matching file in data/raw/ with a
newer export (same filename) and re-run this script. No code changes
needed for a routine data refresh.

Attribution (kept here and wherever this data is displayed in the app):
  - DOAJ:        Directory of Open Access Journals (https://doaj.org)
  - Scopus/WoS:  SCImago Journal & Country Rank (https://www.scimagojr.com)
  - SINTA:       Indonesia's Science and Technology Index
                 (https://sinta.kemdikbud.go.id)
  - Elsevier:    Elsevier Scopus Source List
  - ROAD:        Directory of Open Access Scholarly Resources (https://road.issn.org)
  - ERIH PLUS:   European Reference Index for the Humanities and Social
                 Sciences (https://erihplus.nsd.no)
  - SciELO:      Scientific Electronic Library Online (https://scielo.org)
  - AJOL:        African Journals Online (https://www.ajol.info)
"""

from pathlib import Path

from importers.doaj import DOAJImporter
from importers.scimago import import_scimago
from importers.sinta import import_sinta
from importers.elsevier import import_elsevier
from importers.enrichment.road import ROADProvider
from importers.enrichment.erihplus import ERIHPlusProvider
from importers.enrichment.scielo import SciELOProvider
from importers.enrichment.ajol import AJOLProvider
from importers.enrichment.runner import run_offline_provider
from importers.aliases import import_doaj_aliases, import_elsevier_aliases, import_erihplus_aliases
from services.dedup import JournalIndex
from services.repository import get_connection, count_journals, DB_PATH

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_ENRICHMENT = ROOT / "data" / "enrichment"
SCHEMA_PATH = ROOT / "data" / "schema.sql"


def init_schema():
    conn = get_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def main():

    print(f"Building database at {DB_PATH}")
    print()

    init_schema()

    print("--- DOAJ ---")
    DOAJImporter(DATA_RAW / "doaj.csv").run()
    doaj_count = count_journals()
    print(f"DOAJ: {doaj_count} journals imported")
    print()

    conn = get_connection()
    index = JournalIndex(conn)

    print("--- Scopus (SCImago) ---")
    index, scopus_summary = import_scimago(DATA_RAW / "scimagojr.csv", "Scopus", index=index, conn=conn)
    conn.commit()
    print()

    print("--- Web of Science (SCImago, WoS-filtered) ---")
    index, wos_summary = import_scimago(DATA_RAW / "wos.csv", "Web of Science", index=index, conn=conn)
    conn.commit()
    print()

    print("--- Elsevier Scopus Source List (fills SCImago gaps) ---")
    index, elsevier_summary = import_elsevier(DATA_ENRICHMENT / "Elsevier.csv", "Scopus", index=index, conn=conn)
    conn.commit()
    print()

    print("--- SINTA ---")
    index, sinta_summary = import_sinta(DATA_RAW / "sinta.csv", "SINTA", index=index, conn=conn)
    conn.commit()
    print()

    print("--- Enrichment: ROAD ---")
    run_offline_provider(ROADProvider(DATA_ENRICHMENT / "road.tsv"), conn)
    conn.commit()
    print()

    print("--- Enrichment: ERIH PLUS ---")
    run_offline_provider(ERIHPlusProvider(DATA_ENRICHMENT / "erihplus.csv"), conn)
    conn.commit()
    print()

    print("--- Enrichment: SciELO ---")
    run_offline_provider(SciELOProvider(DATA_ENRICHMENT / "scielo_journals.csv"), conn)
    conn.commit()
    print()

    print("--- Enrichment: AJOL ---")
    run_offline_provider(AJOLProvider(DATA_ENRICHMENT / "ajol.csv"), conn)
    conn.commit()
    print()

    print("--- Journal Aliases (DOAJ, Elsevier, ERIH PLUS) ---")
    import_doaj_aliases(DATA_RAW / "doaj.csv", index, conn)
    import_elsevier_aliases(DATA_ENRICHMENT / "Elsevier.csv", index, conn)
    import_erihplus_aliases(DATA_ENRICHMENT / "erihplus.csv", index, conn)
    conn.commit()
    print()

    conn.close()

    total_journals = count_journals()

    print("=" * 60)
    print("Import summary")
    print("=" * 60)
    print(f"DOAJ imported:       {doaj_count} journals")
    for label, summary in [("Scopus", scopus_summary), ("Web of Science", wos_summary), ("SINTA", sinta_summary)]:
        matched = summary["matched_by_issn"] + summary["matched_by_title"]
        print(f"{label:20} {summary['rows']} rows -> {matched} matched to existing journals, "
              f"{summary['created']} new journals created")
    print(
        f"{'Elsevier':20} {elsevier_summary['rows']} rows -> "
        f"{elsevier_summary['newly_tagged']} newly tagged Scopus (no SCImago rank yet), "
        f"{elsevier_summary['already_tagged']} already Scopus via SCImago"
    )
    print()
    print(f"Total unique journals in database: {total_journals}")
    print()
    print("Validation warnings:")
    for label, summary in [("Scopus", scopus_summary), ("Web of Science", wos_summary), ("SINTA", sinta_summary)]:
        print(f"  {label}: {summary['missing_issn']} rows had no usable ISSN, "
              f"{summary['matched_by_title']} matches were by title only (no ISSN overlap)")


if __name__ == "__main__":
    main()
