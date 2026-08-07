# Design System & Shared Components

## Purpose

Records the visual tokens (colors) and reusable UI components the web
frontend (`web/templates/`) is built from, so new pages and components
stay visually consistent instead of each introducing its own ad-hoc
colors or card styles.

This document is about the *visual* layer only. For UX principles
(Simple/Advanced mode, workflow, accessibility) see UI.md. For why
FastAPI + Jinja2 + HTMX + Tailwind was chosen at all, see
ARCHITECTURE_DECISIONS.md.

---

# Brand Colors

Defined in `tailwind.config.js` under `theme.extend.colors`, used as
Tailwind utility classes (`bg-navy-600`, `text-horizon-600`, etc.).

| Token | Base hex | Role |
|-------|----------|------|
| `navy` | `#1E3A5F` (Navigation Navy) | Reserved for future primary chrome (headers, nav backgrounds) — not yet applied site-wide. |
| `horizon` | `#2F5E88` (Horizon Blue) | Primary interactive accent — links, primary buttons, focus rings, active nav state. Replaces the placeholder `indigo-*` Tailwind default that was used before this document existed. |
| `gold` | `#C9A227` (Guiding Gold) | Reserved for highlight/emphasis accents (e.g. featured content). Not yet applied — available for upcoming pages such as the About page. |

Each color needs more than its base hex because Tailwind utilities
reference specific shades (`horizon-50`, `horizon-500`, `horizon-600`,
`horizon-700`, ...). Shades other than the base are derived
mechanically, not hand-picked, so they stay reproducible:

- **Lighter shade** (e.g. `-50`, `-500`): mix the base RGB with white.
- **Darker shade** (e.g. `-700`, used for `:hover` states): multiply
  each RGB channel by `0.8`.

This is a starting scale, not a final one — if a designer produces a
full hand-tuned palette later, replace these derived values directly
in `tailwind.config.js`; nothing downstream depends on how the shades
were computed, only on the class names.

## Build note

`web/static/css/output.css` is a committed, pre-built Tailwind output
(see WEB_MIGRATION.md — this is intentional, not a checked-in
artifact by accident). Any change to `tailwind.config.js` or to which
utility classes templates use must be followed by
`npm run build:css` to keep it in sync.

---

# Shared Components

All reusable pieces live in `web/templates/components/` as Jinja2
macros, imported by the pages/partials that need them. None of them
contain business logic — they only render data already computed by
`services/` or `web/search_presentation.py`.

| Component | Purpose |
|-----------|---------|
| `journal_card.html` | Renders one journal recommendation: title, confidence badge, source chips, explanation, and an expandable detail section. |
| `recommendation_badge.html` | Small colored badge for a confidence tier (used inside `journal_card`). |
| `index_badge.html` | Small badge for an indexing source (Scopus, SINTA, etc). |
| `stat_card.html` | Centered value + label tile (homepage stats). |
| `feature_card.html` | Icon + title + description tile (homepage feature grid). |
| `workflow_card.html` | Numbered step card with a call-to-action link (homepage "how it works"). |
| `filter_panel.html` | The Advanced Mode filter form fields (indexing, quartile, SINTA level, language, budget). |
| `search_form.html` | Title/abstract/keywords input fields shared by the search page. |
| `search_history.html` | List of past searches from the session, each rerunnable. |
| `pagination.html` | Page-number controls for the results list. |
| `export_panel.html` | The row of export-format buttons (PDF/DOCX/XLSX/MD/CSV). |
| `info_section.html` | Generic titled text block (used on the Academy page). |

## Shared card pattern

Several components (`journal_card`, `stat_card`, `feature_card`,
`workflow_card`) independently use the same base card styling:

```
bg-white rounded-lg border border-gray-200
```

This is a convention, not an enforced abstraction — new components
should match it for visual consistency, but it isn't worth wrapping in
its own macro at the current component count. Revisit if the card
pattern needs to change in more than one place at once.

---

**Document Version:** 0.1

**Last Updated:** August 2026

**Status:** Approved
