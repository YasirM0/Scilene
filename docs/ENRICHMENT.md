# Metadata Enrichment Pipeline (Design)

**Status:** Design only — nothing in this document is wired into the
running app yet. It defines the architecture that `importers/`
providers and their storage will follow once implemented (tracked in
#108 and the dataset-specific issues below). See "What this issue
does *not* do" at the end.

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
| Elsevier Source List | `Elsevier.csv` | Authoritative Scopus indexing + ASJC taxonomy + title history — this one is scoped to #98 (redefining how Scopus indexing itself is determined), not pure enrichment; noted here because the file lives in the same folder |

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

## Proposed storage

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

## Acceptance criteria for this design

- [x] Indexing sources vs. enrichment sources are explicitly
      distinguished, with the rule for which is which.
- [x] Each dataset's responsibility is scoped to one kind of
      information.
- [x] Storage is structurally separate from `journal_sources`, so
      enrichment cannot reach scoring code by accident.
- [x] The provider abstraction is defined (interface only).
- [x] Online vs. offline behavior, including the desktop consent
      flow, is specified.
- [x] The annual regeneration process for API-sourced offline data
      (SciELO, Sherpa Romeo) is specified.

## What this issue does *not* do

- Does not modify `data/schema.sql`, `models/journal.py`, or
  `services/repository.py` — applying the `journal_enrichment` table
  and wiring it in is real implementation work, scoped to #108 and
  the dataset-specific issues (#97 Garuda, #98 Scopus/Elsevier, #100
  aliases), not this design pass.
- Does not implement any provider (no ROAD parser, no ERIH PLUS
  parser, no Crossref/OpenAlex client). Only the abstract
  `EnrichmentProvider` base class exists so far
  (`importers/enrichment/base.py`).
- Does not touch `services/recommender.py` in any way.

---

**Document Version:** 0.1

**Last Updated:** August 2026

**Status:** Proposed
