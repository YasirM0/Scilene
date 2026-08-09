# User Interface Design

## Purpose

The user interface provides a simple and intuitive way for researchers to discover journals that fit their manuscripts.

Version 0.1 focuses on usability, transparency, and speed.

The interface should help users reach a recommendation with minimal effort while allowing advanced users to customize their search.

---

# Design Principles

## Simplicity First

The interface should minimize unnecessary complexity.

A first-time user should be able to obtain recommendations without reading documentation.

---

## Transparency

Recommendations should always be accompanied by an explanation.

Researchers should immediately understand why a journal appears in the results rather than seeing only a numerical assessment.

---

## Progressive Disclosure

Basic functionality should be immediately accessible.

Advanced options should remain available without overwhelming new users.

---

# User Workflow

```
Open Application
        │
        ▼
Choose Search Mode
        │
        ▼
Enter Manuscript Information
        │
        ▼
(Optional) Configure Preferences
        │
        ▼
Search
        │
        ▼
View Recommendations
        │
        ▼
Inspect Journal Details
        │
        ▼
Export Results
```

---

# Search Modes

**Update, v0.2.5:** the Simple Mode fields below reflect the original
v0.1 design. The actual form has since changed — Title was removed
entirely, and Keywords was replaced by the Research Interpreter
("Suggested by Scilene") flow plus a tag-based fallback for users
without an abstract. See `docs/RESEARCH_INTERPRETER.md` for the
current design; this section is left as the original v0.1 record.

## Simple Mode

Designed for researchers who want recommendations quickly.

### Required Fields

- Manuscript Title
- Abstract

### Optional Fields

- Keywords

The system applies default settings and returns ranked recommendations.

---

## Advanced Mode

Allows researchers to customize recommendations.

Additional options include:

- Index selection (Scopus, SINTA)
- Quartile preference
- Maximum APC
- Publication language
- Open Access requirement

Future versions may introduce additional filters.

---

# Recommendation Results

Each recommendation should display:

- Journal Name
- Overall Match
- Top Reasons
- Publisher
- Indexes
- Quartile (if available)
- SINTA Rank (if available)
- APC information
- Publication language
- Open Access status

Each recommendation should also provide a link to the journal's official website.

Example:

```
Journal of Regional Development

Overall Match
92%

Top Reasons

✓ Strong topical similarity
✓ Scopus indexed
✓ No APC
✓ English publication
```

The recommendation should prioritize explanation before numerical assessment.

Researchers should immediately understand why a journal appears in the results.

---

# Journal Details

Selecting a journal should display additional information, including:

- Aims & Scope
- Journal Description
- Subject Areas
- Keywords
- Publication Frequency
- ISSN / eISSN

Future versions may provide a more detailed explanation of how individual ranking factors contributed to the recommendation.

---

# Export

Users should be able to export recommendation results.

Supported formats for Version 0.1:

- CSV
- JSON
- Markdown

Future versions may support additional formats.

---

# Error Handling

The interface should provide clear messages when:

- Required fields are missing.
- No matching journals are found.
- Filters are too restrictive.
- Data is unavailable.

Error messages should explain the problem and, whenever possible, suggest a solution.

---

# Accessibility

The interface should prioritize readability.

Where practical, it should:

- Use clear labels
- Avoid unnecessary jargon
- Support keyboard navigation
- Display important information consistently

Accessibility improvements will continue in future versions.

---

# Out of Scope

Version 0.1 does not include:

- User accounts
- Saved searches (persisted across sessions/devices)
- Cloud synchronization
- AI chat assistant
- Collaboration features

Session-only search history (cleared when the browser session ends,
never written to the database) was added in v0.1.8 — see
docs/RECOMMENDATIONS.md.

---

# Version 0.1 Scope

Version 0.1 provides a lightweight interface that enables researchers to:

- Enter manuscript information
- Configure basic preferences
- Receive transparent journal recommendations
- Understand why journals are recommended
- Review journal information
- Revisit recent searches from the same browser session
- Export results as PDF, DOCX, XLSX, Markdown, or CSV — see
  docs/EXPORT.md

The interface prioritizes clarity, transparency, and usability over feature richness.

---

## Multilingual UI (#84)

Runtime language switching between English, Arabic (RTL), and
Indonesian — a session preference (`web/i18n.py`, like the show-weaker
toggle or dark mode), not a URL prefix, so every route/URL stays
identical regardless of locale.

**What's translated:** navigation, footer, and the homepage — every
string a visitor sees before choosing what to do. Arabic sets
`dir="rtl"` on `<html>`, giving translated text real browser-native
right-to-left flow.

**What's not translated yet:** Submission Search, About, Documentation,
Settings, Statistics, and Compare all still render in English
regardless of the chosen locale — this is a deliberate first slice
(~150 further strings, translated accurately, is real ongoing work),
not an oversight. `<html lang>`/`dir` are still set correctly on every
page even where content isn't translated.

**What's deliberately never translated:** journal metadata (title,
publisher, subjects, ...) — it's factual source data imported verbatim
from DOAJ/Scopus/SINTA; translating it would misrepresent what a
journal actually says about itself.

**RTL scope:** only the pages above get real right-to-left content
flow. This pass does not re-audit every LTR-coded spacing utility
(`ml-*`, `mr-*`, `text-left`, ...) across the rest of the UI into
logical-property equivalents — that's real, separate work belonging to
full translation coverage of each page, not this first pass.

---

**Document Version:** 0.2

**Last Updated:** August 2026

**Status:** Approved — Multilingual UI is a partial, honest slice (see
above), not full coverage.