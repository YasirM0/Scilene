"""
Slim enrichment CSVs to only the columns actually consumed by the importers.

These files are committed to the repo but their source downloads carry
many columns we never read (e.g., all 27 ASJC discipline flags in
Elsevier.csv, citation stats in wos.csv). Dropping them shrinks the
repo significantly without touching any import logic.

Run once after downloading a fresh copy of any source file:
    python scripts/slim_enrichment_csvs.py

The script is idempotent -- running it again on an already-slimmed
file is safe (columns that don't exist are silently skipped).

Column authority for each file is documented here rather than
distributed across the importer modules:
  - importers/elsevier.py (import_elsevier + importers/aliases.py
    import_elsevier_aliases)
  - importers/scimago.py (import_scimago, used for wos.csv)
  - importers/enrichment/erihplus.py (ERIHPlusProvider +
    importers/aliases.py import_erihplus_aliases)
  - importers/enrichment/scielo.py (SciELOProvider)
  - importers/enrichment/ajol.py (AJOLProvider) -- ajol.csv is ~100KB,
    skipped here since every column is used anyway
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
ENRICHMENT = ROOT / "data" / "enrichment"


def _slim(path, keep_cols, sep=",", encoding="utf-8-sig", note=""):
    if not path.exists():
        print(f"  SKIP  {path.name} (not found)")
        return

    before = path.stat().st_size
    df = pd.read_csv(path, sep=sep, encoding=encoding, dtype=str)

    # Dynamic columns (e.g. "Added to List June 2026") -- keep any
    # column whose name starts with a known prefix even if the exact
    # name changes between annual releases.
    dynamic_prefixes = keep_cols.get("__prefixes__", [])
    dynamic_cols = [
        c for c in df.columns
        if any(c.startswith(p) for p in dynamic_prefixes)
    ]

    static_cols = [c for c in keep_cols.get("__static__", []) if c in df.columns]
    final_cols = static_cols + [c for c in dynamic_cols if c not in static_cols]

    missing = [c for c in keep_cols.get("__static__", []) if c not in df.columns]
    if missing:
        print(f"  WARN  {path.name}: expected columns not found: {missing}")

    df = df[final_cols]
    df.to_csv(path, index=False, sep=sep, encoding=encoding)

    after = path.stat().st_size
    saved_mb = (before - after) / 1_048_576
    pct = 100 * (before - after) / before if before else 0
    tag = f"  [{note}]" if note else ""
    print(f"  OK    {path.name}: {before/1_048_576:.1f} MB -> {after/1_048_576:.1f} MB  "
          f"(saved {saved_mb:.1f} MB, {pct:.0f}%){tag}")


ELSEVIER_COLS = {
    "__static__": [
        # matching
        "Sourcerecord ID",
        "Source Title",
        "ISSN",
        "EISSN",
        # indexing status + coverage window
        "Active or Inactive",
        "Coverage",
        # language enrichment (#89)
        "Article Language in Source (Three-Letter ISO Language Codes)",
        # publication type (#128)
        "Source Type",
        # alias / title history (importers/aliases.py import_elsevier_aliases)
        "Title History Indication",
        "Related Title 1",
        "Other Related Title 2",
        "Other Related Title 3",
        "Other Related Title 4",
    ],
    # "Added to List June 2026" -- Elsevier bakes the snapshot vintage
    # into the column name itself; detect by prefix so a future release
    # with a different month/year still gets kept automatically.
    "__prefixes__": ["Added to List "],
}

# wos.csv shares the raw SCImago semicolon-separated export format with
# data/processed/scimago_complete.csv, but unlike that file it has no
# appended index_terms column (row.get("index_terms") returns None
# silently, which is correct -- WoS rows get no index-term data here).
WOS_COLS = {
    "__static__": [
        # dedup (importers/scimago.py checks seen_source_ids)
        "Sourceid",
        # matching
        "Title",
        "Issn",
        # insert_minimal_journal when row doesn't match an existing journal
        "Publisher",
        "Country",
        # ranking metadata stored in journal_sources
        "SJR Best Quartile",
        "SJR",
        "H index",
        # enrichment flag (#98)
        "Open Access Diamond",
    ],
    "__prefixes__": [],
}

ERIHPLUS_COLS = {
    "__static__": [
        # matching (ERIHPlusProvider.fetch + import_erihplus_aliases)
        "tidsskriftISSNP",
        "tidsskriftISSNE",
        # aliases (importers/aliases.py import_erihplus_aliases)
        "navn",
        "navn_en",
        # enrichment data (ERIHPlusProvider._load)
        "forlag_navn",
        "url",
        "oa_doaj",
        "oa_romeo",
    ],
    "__prefixes__": [],
}

SCIELO_COLS = {
    "__static__": [
        # matching
        "scielo_issn",
        # enrichment data (SciELOProvider._load)
        "publisher_name",
        "current_status",
        "subject_areas",
        "mission",
        # "collection" and "title" are not read by any importer
    ],
    "__prefixes__": [],
}


def main():
    print("Slimming enrichment CSVs (keeping only importer-consumed columns)...\n")

    _slim(ENRICHMENT / "Elsevier.csv", ELSEVIER_COLS,
          sep=",", encoding="utf-8-sig",
          note="drops 38 ASJC + Medline + OA-status columns")

    _slim(ENRICHMENT / "wos.csv", WOS_COLS,
          sep=";", encoding="utf-8",
          note="drops citation stats, rank, region, areas, categories")

    _slim(ENRICHMENT / "erihplus.csv", ERIHPLUS_COLS,
          sep=",", encoding="utf-8-sig",
          note="drops discipline IDs, language, OECD, date flags")

    _slim(ENRICHMENT / "scielo_journals.csv", SCIELO_COLS,
          sep=",", encoding="utf-8",
          note="drops collection + title columns")

    print("\najol.csv: skipped — 100 KB, all columns are consumed by AJOLProvider")
    print("\nDone. Re-run after any future source CSV download to keep sizes minimal.")


if __name__ == "__main__":
    main()
