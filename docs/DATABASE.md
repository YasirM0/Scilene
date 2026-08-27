# Database: schema, import pipeline, and merge strategy

## Schema

**`journals`** — one row per real-world journal, regardless of how many
indexes it appears in. Core metadata (title, publisher, country, ISSNs,
subjects, APC, license, review time, ...) comes from whichever source
had the richest data for that journal — in practice, DOAJ first, then
Scopus/SINTA metadata is used to fill in journals DOAJ doesn't have.
`publication_type` (#128) is the one exception with its own resolution
rule rather than "richest source wins": only the Elsevier Source List
populates it (its "Source Type" column — in the real dataset, only
"Journal"/"Book Series"/"Trade Journal" occur); a journal Elsevier
hasn't matched shows as "Journal" if it's DOAJ-sourced (DOAJ's whole
scope is journals, so that's a real fact, not a guess) or "Other"
otherwise — see `utils/publication_types.py`.

**`journal_sources`** — one row per (journal, source) pair. This is what
makes the model source-agnostic: a journal with rows for `DOAJ`,
`Scopus`, and `Web of Science` is still ONE row in `journals`, tagged
three times here. Source-specific metadata that doesn't apply to every
source lives here too (`quartile`, `sjr`, `h_index` for Scopus/WoS;
`accreditation` for SINTA) and is simply NULL where it doesn't apply.

Indexes exist on `issn_print`, `issn_online`, `title`, `country`
(journals) and `journal_id`, `source` (journal_sources) for query speed.

## Supported collections (v0.1.x)

| Source | File | Role |
|---|---|---|
| DOAJ | `data/processed/doaj_complete.csv` | Base catalog — richest per-journal metadata |
| Scopus | `data/processed/scimago_complete.csv` | Tags + quartile/SJR/H-index, via SCImago |
| Web of Science | `data/enrichment/wos.csv` | Tags + quartile/SJR/H-index — the SAME SCImago format, pre-filtered by the maintainer to WoS-indexed journals only. Lives in `data/enrichment/` rather than `data/processed/` since it's derived from `scimagojr.csv`, not an independent primary-source export |
| SINTA | `data/processed/sinta_complete.csv` | Tags + accreditation tier (SINTA 1–6) |

The three `data/processed/*_complete.csv` files are their `data/raw/`
counterparts (`doaj.csv`, `scimagojr.csv`, `sinta.csv`) plus appended
`scope`/`index_terms` enrichment columns — every column an importer
actually reads keeps its original raw name, so these are safe drop-in
replacements built directly from the raw exports, not a different
schema. None of `data/processed/`'s complete exports or
`data/enrichment/`'s `wos.csv` are committed to this repo — large,
license-bound source data, kept out of git and out of the deployed app
entirely (only the already-built `data/journal_intelligence.db` ships;
the live app never reads these CSVs). Restore them with `python -m
scripts.fetch_source_csvs` (see that script's own docstring for the
required `HF_TOKEN`) before running a rebuild on a fresh clone —
that same command also restores the original `data/raw/` exports, kept
purely as a provenance backup since `scripts/build_database.py` itself
reads from `data/processed/`.

Not yet supported: Google Scholar (no bulk export exists to import from
— there's nothing to build a real filter against), OpenAlex, Crossref,
Sherpa Romeo. Adding a new source means writing one importer following
the same pattern as `importers/scimago.py` or `importers/sinta.py`, not
changing the schema.

A fourth table, `journal_enrichment`, holds display-only metadata
(ROAD, ERIH PLUS, SciELO, AJOL) that can never affect search,
filtering, or ranking — deliberately kept separate from the two tables
above. See `docs/ENRICHMENT.md`.

A fifth table, **`journal_aliases`**, holds alternate/historical
titles — DOAJ alternative titles, Elsevier former/continued/related
titles, ERIH PLUS original & English titles (one row per (journal,
alias, source), see `importers/aliases.py`). Unlike `journal_enrichment`,
this table DOES affect search and import-time matching, but only as a
fallback:

- `services/repository.py`'s `search_candidates()` matches a keyword
  against `journal_aliases.alias` with the exact same deterministic
  `LIKE` pattern it already uses for `title`/`subjects`/`keywords` —
  it's additive, never a separate ranking signal.
- `services/dedup.py`'s `JournalIndex.find()` tries an alias match only
  once ISSN and primary-title matching have both failed, under the
  same word-count and country guards a title match requires (see
  Deduplication / merge strategy below).

Each alias keeps its `alias_type` (e.g. "Formerly known as", "English
title") and `source`, so provenance is never lost. A journal card shows
at most one alias, in a secondary style below the title.

Not yet wired: ROAD/Crossref/OpenAlex/Wikidata as alias sources (the
schema supports it — one more `import_*_aliases()` function, no schema
change), and aliases are not used by `importers/scimago.py` /
`importers/sinta.py` / `importers/elsevier.py`'s own matching passes,
since `importers/aliases.py` runs after them in the build pipeline.

Separately, `importers/elsevier.py` uses the Elsevier Scopus Source
List to fill Scopus-indexing gaps SCImago's snapshot hasn't caught up
to yet (writes to `journal_sources`, same as SCImago — this one DOES
affect the Scopus filter). See `docs/ENRICHMENT.md`'s Elsevier note.

## Import pipeline

Run `python3 scripts/build_database.py` from the project root. This is
a **full rebuild**: it drops and recreates every table, then imports
the base sources in order (DOAJ → Scopus → Web of Science → Elsevier →
SINTA), tags display-only enrichment (ROAD, ERIH PLUS, SciELO, AJOL),
and finally imports aliases (DOAJ, Elsevier, ERIH PLUS — see
`journal_aliases` above) once every journal that could match one
already exists. To refresh any dataset, replace the matching file in
`data/processed/` or `data/enrichment/` (same filename) and re-run the
script — no code changes needed for a routine data update.

## Deduplication / merge strategy

The database intentionally uses a **conservative merge strategy**. False
duplicates are considered more harmful than leaving two records
unmerged, because an incorrect merge can attach the wrong indexing,
quartile, or accreditation information to a journal.

For each incoming row (Scopus, WoS, SINTA):

1. Try to match an existing journal by ISSN (print or online). This is
   the authoritative matching method.
2. If no ISSN match exists, try an **exact normalized-title match**
   **only if**:
   - the title is sufficiently distinctive (generic one- or two-word
     titles such as *Vision*, *Forum*, or *Logos* are intentionally
     excluded), and
   - the existing journal and incoming record do not have conflicting
     country metadata.
3. If neither rule matches, create a new row in `journals` and attach
   the source normally.

This is intentionally **not fuzzy matching**. Two records referring to
the same journal but using different titles (for example subtitles,
alternative transliterations, abbreviations, or translations) will
remain separate until a reliable identifier such as an ISSN can confirm
they are the same journal.

`scripts/build_database.py` reports how many journals matched by ISSN
and how many required the title fallback. A high number of title-based
matches should always be reviewed manually because they carry a higher
risk of false positives than ISSN matches.

### Lessons learned

Early versions allowed any exact normalized title to trigger a merge.
Testing revealed several false positives involving journals with generic
titles (for example *Vision*, *Forum*, and *Logos*), causing unrelated
journals from different countries to inherit incorrect indexing
information.

The current strategy restricts title-based merges to distinctive titles
and rejects matches with conflicting country metadata. After rebuilding
the database, all previously identified false title merges were
eliminated. The remaining title-independent merges are backed by shared
ISSNs and are therefore considered legitimate.

### What actually happened on the last real build

From `data/raw/doaj.csv` (23,077), `scimagojr.csv` (32,193 Scopus
rows), `wos.csv` (17,815 WoS rows — a subset of the Scopus file), and
`sinta.csv` (15,453 rows):

- DOAJ: 23,077 journals (base catalog)
- Scopus: 9,194 matched an existing DOAJ journal; 22,999 had no DOAJ
  match and became new journal rows (expected — DOAJ is open-access
  only, Scopus is much broader)
- Web of Science: all 17,815 rows matched something already in the
  database (0 new) — expected, since this file is a subset of the
  Scopus file already imported; this is a useful sanity check that the
  matching logic is working
- SINTA: 5,989 matched; 9,464 became new rows (mostly lower-tier
  Indonesian journals not indexed elsewhere)
- **Total: 55,540 unique journals**

## Attribution

- **DOAJ**: journal-level metadata (the CSV this project imports) is
  released under a **CC0 waiver** — no attribution is legally required
  — per DOAJ's own terms: https://www.doaj.org/terms/. Crediting it is
  still good practice and is shown in the app regardless.
- **Scopus / Web of Science data (via SCImago)**: SCImago's own site
  states their data may be used for non-commercial purposes **as long
  as it is cited**: "SCImago, (n.d.). SJR — SCImago Journal & Country
  Rank [Portal]. Retrieved from https://www.scimagojr.com". This is a
  real requirement, not a courtesy — keep the citation wherever this
  data is shown or redistributed, and keep usage non-commercial.
- **SINTA**: no official bulk-export terms exist; this dataset is a
  maintainer-run scrape of https://sinta.kemdikbud.go.id/journals, not
  an official SINTA download. Worth keeping in mind if this project (or
  its database) is ever shared outside your own use.

The Streamlit search page shows a data-source credit line at the bottom
of every results view.

## Architecture note

`services/recommender.py` and `services/repository.py` do not import
Streamlit and can be used from a script or another frontend.
`services/search_service.py` is the intended entry point for any UI —
Streamlit pages should call it instead of touching the recommender or
repository directly. This is a first pass at that separation, scoped to
what the search page needed; other pages haven't been touched yet.
