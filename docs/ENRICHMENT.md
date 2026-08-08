# Metadata Enrichment Pipeline

**Status:** Implemented for all four offline providers (ROAD, ERIH
PLUS, SciELO, AJOL) plus surfacing enrichment in the UI — see "Current
implementation state" at the end for exactly what that does and
doesn't cover. It's the foundation `importers/enrichment/` providers
and their storage follow (tracked in #108 and the dataset-specific
issues below).

---

## The core distinction

Journal Intelligence already has one pipeline: `importers/` builds
`journals` + `journal_sources` (see `docs/DATABASE.md`), and every row
there can affect **search, filtering, or ranking** — a Scopus
quartile changes a score, a SINTA accreditation is filterable.

Metadata enrichment is a **second, separate concept**, not a bigger
version of the first one. Its one rule, straight from the project's
"Offline First" and "Evidence Before Assumptions" principles
(`docs/ARCHITECTURE.md`):

> Enrichment data may only be *displayed*. It must never change which
> journals are found, how they're filtered, or how they're scored.

Concretely: an enrichment provider's data can never be read by
`services/recommender.py`. If a future need would require that, it's
an indexing source (like DOAJ/Scopus/SINTA today), not enrichment —
a different, much higher bar, since it would mean the data directly
shapes what a researcher sees as "recommended."

| | Indexing source (existing) | Enrichment source (this design) |
|---|---|---|
| Examples | DOAJ, Scopus, Web of Science, SINTA | ROAD, ERIH PLUS, SciELO, AJOL, Crossref, OpenAlex, Sherpa Romeo |
| Affects ranking/filtering? | Yes | Never |
| Required for a journal to appear in results? | Can be (a filter) | Never |
| When is it fetched? | Database build time only | Database build time (offline datasets) or on-demand (online APIs) |
| Storage | `journals` + `journal_sources` | New `journal_enrichment` table (below) — kept structurally separate on purpose |

---

## Dataset responsibilities

Local files already collected for this, in `data/enrichment/`:

| Dataset | File | Provides |
|---|---|---|
| ROAD | `road.tsv` (tab-separated — the importer needs a TSV reader, not just CSV) | Additional indexing coverage flag, ISSNs, publisher |
| ERIH PLUS | `erihplus.csv` | ERIH PLUS indexing flag, English title, publisher, URL, DOAJ/Sherpa Romeo flags |
| SciELO | `scielo_journals.csv` | Regional (Latin America) coverage, subject areas, mission statement |
| AJOL | `ajol.csv` | African journal coverage, Diamond OA flag |
| Garuda | `data/raw/sinta.csv`'s `garuda_indexed` column (#97) | Indonesian national repository indexing flag. Tagged directly in `importers/sinta.py` rather than its own `importers/enrichment/` provider, since the data arrives bundled in the SINTA file, not a separate one — same `journal_enrichment` storage and same rule (display-only, never a search filter, never affects ranking) as every other provider here. |
| Elsevier Source List | `Elsevier.csv` | **Not enrichment** — scoped to #98 (redefining how Scopus indexing itself is determined). Implemented narrowly: `importers/elsevier.py` fills Scopus-indexing gaps SCImago's periodic snapshot hasn't caught up to yet, without touching quartile/SJR/H-index. The rest of #98 (title history, ASJC taxonomy, article language, coverage display, Source Record ID, import-order restructuring) is NOT implemented — see "Current implementation state". |

Not yet available locally (per the original issue, these must never
require a live call from the *offline* app — see "Online vs. offline"
below):

| Dataset | Source | Notes |
|---|---|---|
| Crossref | Live API, online-only | Generated to a local CSV during annual updates for offline use; live-queried opportunistically by the web app |
| OpenAlex | Live API, online-only | Same pattern as Crossref |
| Sherpa Romeo | Live API, used only during annual updates | The running app must never depend on a live Sherpa Romeo call — API terms and the issue both require this |

Each dataset owns one clearly-scoped kind of information — no two
enrichment sources should be asked "is this journal Scopus indexed,"
that question belongs to the indexing pipeline (`docs/DATABASE.md`),
not here.

---

## Storage

A single wide table, one row per `(journal_id, provider)` pair —
deliberately separate from `journal_sources` so a bug in enrichment
code structurally cannot alter a score or a filter result (there is
no code path from this table into `services/recommender.py`):

```sql
CREATE TABLE journal_enrichment (
    journal_id INTEGER NOT NULL,
    provider TEXT NOT NULL,       -- 'road', 'erihplus', 'scielo', 'ajol', 'crossref', 'openalex', 'sherpa_romeo'
    fetched_at TEXT,              -- NULL for offline/static providers
    data TEXT NOT NULL,           -- JSON blob; shape is provider-specific, display-only

    PRIMARY KEY (journal_id, provider),
    FOREIGN KEY (journal_id) REFERENCES journals(id)
);

CREATE INDEX idx_journal_enrichment_journal_id ON journal_enrichment(journal_id);
```

A JSON blob (rather than a fixed set of columns) because each
provider's fields genuinely differ (ERIH PLUS's DOAJ/Sherpa Romeo
flags vs. SciELO's mission statement vs. Crossref's live-fetched
fields) and none of it needs to be queried or filtered on — only
displayed once a journal is already found. If a future need requires
querying enrichment data, that's a sign it should be a real column
(and probably a sign it's not enrichment anymore — see the table
above).

## Provider abstraction

A new sibling to `importers/base.py`'s `BaseImporter`, not a subclass
of it — enrichment providers don't produce `Journal` rows, they
attach data to journals that already exist:

```python
# importers/enrichment/base.py

class EnrichmentProvider:
    """
    Parent class for all metadata enrichment providers.

    Unlike BaseImporter (which creates/updates rows in `journals`),
    a provider only ever attaches data to a journal that already
    exists — matched by ISSN, the same authoritative method
    `docs/DATABASE.md` uses for deduplication. A provider that can't
    match a journal by ISSN skips it; enrichment never creates a new
    journal or guesses a match.
    """

    name: str = ""  # matches journal_enrichment.provider

    def fetch(self, journal):
        """
        Retrieve this provider's data for one journal (dict, or None
        if unavailable). Online providers call an API here; offline
        providers look up a pre-loaded local dataset.
        """
        raise NotImplementedError

    def is_online(self) -> bool:
        raise NotImplementedError
```

`OfflineEnrichmentProvider` (ROAD, ERIH PLUS, SciELO, AJOL — and the
annually-regenerated Crossref/OpenAlex/Sherpa Romeo CSVs) reads a
local file and runs during `scripts/build_database.py`, same as
today's importers. `OnlineEnrichmentProvider` (Crossref, OpenAlex —
live) runs on demand, after search results already exist, and is
subject to the permission flow below. Actual provider
implementations (the ISSN-matching logic, each dataset's specific
field mapping, caching, retries) belong to their own issues (#108,
and the dataset-specific issues), not this design pass.

---

## Online vs. offline behavior

This is the one place the design has to branch by which frontend is
running, because the two have different defaults per
`docs/ARCHITECTURE.md`'s "Privacy First" principle:

- **Web app**: already requires an internet connection to be reached
  at all. Online enrichment (Crossref/OpenAlex) may be fetched
  automatically. No permission dialog.
- **Desktop app** (once it exists — see `docs/ARCHITECTURE_DECISIONS.md`,
  currently not being built): offline by default. Before making any
  online enrichment call, show:

  > "Additional journal information is available from Crossref and
  > OpenAlex. Retrieving this information requires a temporary
  > internet connection. These services provide supplementary
  > metadata only and do not affect journal recommendations. Continue?"

  With **Continue** / **Skip**. Skipping must leave the app fully
  functional — enrichment is additive, never a dependency.

---

## Annual update process

Per the original issue, the long-term generator layout:

```
tools/
    generate_scielo.py       # SciELO API -> local CSV
    generate_sherpa.py       # Sherpa Romeo API -> local CSV
    build_database.py        # existing: orchestrates the full rebuild
```

No runtime API calls should ever be required for the offline
(desktop) application — SciELO and Sherpa Romeo data is always
pre-generated, never live-queried by the running app itself. Crossref
and OpenAlex are the only two providers ever called live (web
always, desktop only after explicit consent).

---

## Current implementation state

Done:

- `journal_enrichment` table exists in `data/schema.sql` and is
  populated by `scripts/build_database.py` after the core import.
- `services/repository.tag_enrichment()` (upsert, mirrors `tag_source`),
  plus `count_by_enrichment_provider()` for display stats.
- `EnrichmentProvider` / `OfflineEnrichmentProvider` /
  `OnlineEnrichmentProvider` base classes (`importers/enrichment/base.py`).
- Four working offline providers: ROAD, ERIH PLUS, SciELO
  (`importers/enrichment/scielo.py`, parses the mission-statement dict
  literal via `ast.literal_eval`), and AJOL
  (`importers/enrichment/ajol.py`, not in the original issue text —
  the data file was collected afterward). All ISSN-matched only, all
  skip unmatched rows rather than creating journals.
- `importers/enrichment/runner.py` (`run_offline_provider`) drives an
  offline provider over every journal already in the database.
- `importers/elsevier.py` (`import_elsevier`) — the narrow slice of
  #98 described above. Verified against a real rebuild: 142 journals
  newly tagged Scopus-indexed with no SCImago rank yet, 30,689 already
  Scopus-tagged journals left untouched (quartile/SJR/H-index
  preserved, spot-checked).
- Enrichment now reaches the UI: `models/journal.py`'s `Journal.enrichment`
  field, batch-fetched by `services/repository._fetch_enrichment()`
  (same pattern as `_fetch_sources`), passed through
  `services/recommender.py` display-only (not read by any scoring
  code), and rendered as "Also listed in: ..." badges on
  `journal_card.html` — visually distinct from the indexing-source
  checkmark row on purpose. The homepage's "Supported Indexes &
  Coverage" section is now a right-to-left auto-scrolling strip of
  all 8 sources (`.marquee-track`, pure CSS, pauses on hover, respects
  `prefers-reduced-motion`).
- Fixed a latent pre-existing bug surfaced while testing this: an
  unfiltered search (~55k journals) blew past SQLite's per-statement
  variable limit in `_fetch_sources`'s `IN (...)` query. Both
  `_fetch_sources` and the new `_fetch_enrichment` now batch in
  chunks of 500.
- Verified against a real full rebuild: DOAJ/Scopus/WoS/SINTA row
  counts are unchanged from the pre-enrichment baseline, and the
  recommender smoke test (`python -m tests.test_recommender`) returns
  the same top matches with the same scores before and after —
  confirming enrichment cannot influence recommendation results, per
  the design's core rule.

Not done (still real implementation work, not this pass):

- Crossref and OpenAlex (`OnlineEnrichmentProvider`) — need actual
  HTTP calls, caching, retries, and timeout handling.
- The desktop consent flow and "Settings page integration" from
  #108's checklist — blocked on the desktop app existing at all
  (see `docs/ARCHITECTURE_DECISIONS.md`).
- The `tools/generate_scielo.py` / `generate_sherpa.py` annual
  regeneration scripts.
- The rest of #98: title history, ASJC taxonomy, article language,
  coverage display for inactive journals, Source Record ID as the
  canonical identifier, and reordering the import pipeline to put
  Elsevier first. What's implemented only fills the specific gap
  (Scopus-indexed-but-not-yet-ranked) the Elsevier file was collected
  for.

---

**Document Version:** 0.2

**Last Updated:** August 2026

**Status:** Approved (ROAD, ERIH PLUS) — remaining providers pending
