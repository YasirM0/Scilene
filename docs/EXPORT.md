# Recommendation Export (#57)

## Supported formats

| Format | Library | Notes |
|---|---|---|
| PDF | `fpdf2` | Bundled DejaVu Sans font (see below) for Unicode support |
| DOCX | `python-docx` | Full Unicode, no special handling needed |
| XLSX | `openpyxl` (via pandas) | Two sheets: Search Info, Recommendations |
| Markdown | stdlib only | Plain, clean formatting — meant for pasting into an AI assistant |
| CSV | stdlib/pandas (already existed) | Metadata block added as `#`-commented lines |

All five are pure Python — no LibreOffice, pandoc, or wkhtmltopdf — so they
work as-is on Streamlit Community Cloud with no system packages installed.

## Every export includes

- Search title, abstract, keywords, strategy, and applied filters
- A small metadata header (app version, generated-at timestamp, database
  sources, total recommendation count)
- Per journal: confidence level, indexing (DOAJ/Scopus/WoS/SINTA, with
  quartile/accreditation where applicable), publisher, country, APC,
  language, review time, the natural-language "Why this journal?"
  explanation, journal website, and DOAJ URL

## Metadata block

Every format shows the same small header, e.g.:

```
Journal Intelligence v0.1.9
Generated: 2026-07-25 11:45 UTC

Search Strategy: Balanced
Database Sources: DOAJ, Scopus, Web of Science, SINTA
Total Recommendations: 15
```

The timestamp is always labeled UTC and generated via
`datetime.now(timezone.utc)`, not the server's local clock or an assumed
timezone — Streamlit Community Cloud's containers run in UTC, and
labeling it anything else without knowing the actual deployment timezone
would be a guess presented as a fact.

## Architecture

New modules, none of which import Streamlit — reusable from a script, a
future FastAPI backend, or a Tauri desktop app exactly as they are:

- `services/app_info.py` — `APP_VERSION`, `DATABASE_SOURCES`. Single
  place to bump the version string.
- `services/report_context.py` — `ReportContext` (bundles search title/
  abstract/keywords/strategy/filters/results/timestamp/version) and
  `build_filters_summary()` (turns the search page's raw filter values
  into human-readable lines, e.g. `"Budget: up to $100"`).
- `services/reports.py` — `generate_pdf`, `generate_docx`,
  `generate_xlsx`, `generate_markdown`. Each takes a `ReportContext` and
  returns bytes. `generate_xlsx` reuses `recommendations_to_rows()` from
  `services/export.py` so CSV and XLSX never disagree on columns.
- `utils/indexing.py` — `format_source_chip()` / `format_index_summary()`,
  shared by both the on-screen index chips and every export format, so
  the two can't drift apart (extracted from the search page during this
  milestone, previously duplicated logic).

The search page (`app/pages/1_Submission_Search.py`) only calls into
these — it builds no report content itself. Generation is wrapped in a
`st.cache_data`-decorated function keyed by format + search
title/abstract/keywords/strategy/filters + the specific journal ids in
the result set (not the full result list itself, which would be slow to
hash on every pagination click or checkbox toggle).

## A real bug found and fixed during this work

The bundled font (DejaVu Sans, chosen for broad Latin/Cyrillic/Greek
coverage without adding a huge dependency) doesn't support Arabic-family
script shaping or have CJK/Hangul glyphs. Verified directly: letting
fpdf2 attempt an unsupported character doesn't just fail that one
line — it corrupts the whole PDF's internal cursor state, breaking
every entry written afterward, including previously-fine ones. Fixed by
pre-filtering text against the font's own glyph set plus a small
regex for scripts that need shaping fpdf2 can't do, transliterating to
ASCII before anything reaches fpdf2 — never a try/except after the
fact. Stress-tested against all 1,767 real non-Latin-script journal
titles in the database (Cyrillic, Persian/Arabic, Thai, CJK, Hangul)
plus emoji, with zero failures. This is a real, disclosed limitation of
the PDF format specifically — DOCX/XLSX/Markdown have no such issue,
since none of them depend on a font's glyph coverage.

## New dependencies

Added to `requirements.txt`: `python-docx==1.1.2`, `openpyxl==3.1.5`,
`fpdf2==2.8.2`. All pure Python, no system packages required.

New asset: `assets/fonts/DejaVuSans.ttf` (+ Bold/Oblique variants),
bundled for PDF generation.

## Usage example (outside Streamlit)

```python
from services.recommender import JournalRecommender
from services.report_context import ReportContext, build_filters_summary
from services.reports import generate_markdown

recommender = JournalRecommender()
results = recommender.recommend(
    title="Digital Governance and Public Policy",
    keywords=["governance", "digital", "policy"],
)

context = ReportContext(
    title="Digital Governance and Public Policy",
    abstract="A study of digital governance frameworks...",
    keywords=["governance", "digital", "policy"],
    strategy_label="Balanced",
    filters_summary=build_filters_summary(language="English"),
    results=results[:50],
)

markdown_bytes = generate_markdown(context)
```

## Future direction (noted, not built here)

The person maintaining this project has flagged a future migration to
FastAPI + HTMX + Jinja2 + Tailwind, and possibly a Tauri desktop app
after that. Nothing in this milestone changes course for that — every
module listed above already has zero Streamlit imports, which is
exactly the seam a FastAPI backend or a Tauri app would call into
instead of a Streamlit page. That migration itself is a separate,
substantial piece of work and was not started as part of this
milestone.
