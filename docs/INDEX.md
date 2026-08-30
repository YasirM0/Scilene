# Documentation Index

This document provides an overview of the project's documentation.

New contributors are encouraged to begin with the README before exploring the documents listed below.

---

# Getting Started

## README.md

The project's main introduction.

Read this first to understand:

- What Scilene is
- Why it exists
- Current project status
- Planned features
- How to contribute

---

# Project Vision

## VISION.md

Defines the mission, long-term vision, and scope of the project.

Read this to understand *why* the project exists.

---

## PROJECT_PRINCIPLES.md

Defines the core principles that guide every design decision.

Whenever a new feature is proposed, contributors should verify that it aligns with these principles.

---

## DECISIONS.md / ARCHITECTURE_DECISIONS.md

Records significant product and architectural decisions and the
reasoning behind them, so contributors understand not just *what* was
decided but *why*. ARCHITECTURE_DECISIONS.md is the running log by
date; DECISIONS.md covers a handful of the larger, named decisions in
more narrative depth.

---

# System Design

## ARCHITECTURE.md

Describes how the system is organized into independent modules and how those modules interact.

---

## DATABASE.md

Defines the journal data model and explains what information the system stores.

---

## RANKING.md

Explains how journal recommendations are calculated and how ranking remains transparent.

---

## RECOMMENDATIONS.md

Documents what `services/recommender.py` actually does today — scoring,
strategies, prestige, confidence tiers — code-level detail one layer
below RANKING.md's conceptual explanation. Code is the source of truth;
if this drifts from `recommend()`, trust the code.

---

## EXPORT.md

Documents the recommendation export feature (#57) — the five supported
formats (PDF, DOCX, XLSX, Markdown, CSV), what every export includes,
and the modules involved (`services/reports.py`,
`services/report_context.py`). Written during the Streamlit era; a
status note at the top points to where export lives now
(`web/routers/search.py`).

---

## UI.md

Defines the user experience, including Simple Mode and Advanced Mode.

---

## DESIGN_SYSTEM.md

Defines the visual tokens (brand colors) and the shared Jinja2
components the web frontend is built from.

---

## DATA_SOURCES.md

Lists the public sources used to collect journal metadata and explains their intended use.

---

## ENRICHMENT.md

Design for the metadata enrichment pipeline (ROAD, ERIH PLUS, SciELO,
AJOL, Crossref, OpenAlex, Sherpa Romeo) — how it stays structurally
separate from anything that affects search, filtering, or ranking.

---

# Development

## ROADMAP.md

Describes the project's planned milestones and future releases.

---

## CONTRIBUTING.md

Explains how developers can contribute to the project.

---

## DEPLOYMENT.md

Explains the CI pipeline and how to deploy the app (Docker or Heroku).

---

## BENCHMARK.md

Defines how Scilene evaluates changes to its recommendation engine and
AI components — Recall@K/MRR against real published papers, so
improvements are backed by evidence rather than intuition.

---

## WEB_MIGRATION.md

History of the v0.2.0 migration from Streamlit to FastAPI + Jinja2 +
HTMX + Tailwind. The Streamlit app (`app/`) described throughout as
"kept running" has since been deleted outright — see the doc's own
later update note.

---

## AI_ARCHITECTURE.md

Design for Scilene's optional AI layer (#106) — philosophy, candidate
models, reliability rules, and the `AIProvider` interface. No real
model is wired in yet.

---

## RESEARCH_INTERPRETER.md

Architecture for the "Suggested by Scilene" tag-suggestion UI. Key
Research Focus is real, deterministic keyword-vocabulary matching
today (not a placeholder); Field of Study stays non-interactive
example text because its underlying vocabulary proved too coarse. Also
documents why this is built as server-rendered HTMX state rather than
client-side JavaScript.

---

## QUERY_PIPELINE.md

Design for the full query-normalization pipeline (#109) — language
detection, translation, normalization, keyword expansion, and
discipline detection, mapped honestly against what's real today (#89
language detection, #102 discipline detection) vs. genuinely
unimplemented (translation, expansion). Defines the canonical search
representation and states precisely why none of it can influence
ranking.

---

## DOCUMENTATION_TEMPLATE.md

Meta-documentation: the standard structure new documentation files in
this project should follow. Not every document needs every section —
authors should include only what improves clarity for that specific
subject.

---

# Documentation Status

| Document | Status |
|----------|--------|
| README | ✅ Approved |
| VISION | ✅ Approved |
| PROJECT_PRINCIPLES | ✅ Approved |
| ARCHITECTURE | ✅ Approved |
| DATABASE | ✅ Approved |
| DECISIONS | ✅ Approved |
| ARCHITECTURE_DECISIONS | ✅ Approved |
| RANKING | ✅ Approved |
| RECOMMENDATIONS | ✅ Approved |
| EXPORT | ✅ Approved (Streamlit-era doc, still accurate — see its own status note) |
| UI | ✅ Approved |
| DESIGN_SYSTEM | ✅ Approved |
| DATA_SOURCES | ✅ Approved |
| ENRICHMENT | ✅ Approved |
| ROADMAP | ✅ Approved |
| CONTRIBUTING | ✅ Approved |
| DEPLOYMENT | ✅ Approved |
| BENCHMARK | ✅ Approved |
| WEB_MIGRATION | ✅ Approved (historical record) |
| RESEARCH_INTERPRETER | 🟡 Partial — Key Research Focus real, Field of Study non-interactive |
| AI_ARCHITECTURE | 🟡 Design only |
| QUERY_PIPELINE | 🟡 Design only |
| DOCUMENTATION_TEMPLATE | ✅ Approved (meta) |

---

## Reading Order

New contributors are encouraged to read the documentation in the following order:

1. README
2. VISION
3. PROJECT_PRINCIPLES
4. ARCHITECTURE
5. DATABASE
6. RANKING
7. UI
8. DATA_SOURCES
9. ROADMAP
10. CONTRIBUTING

Following this order provides both the motivation behind the project and the technical details required for contribution.

---

**Document Version:** 0.1

**Last Updated:** July 2026

**Status:** Approved