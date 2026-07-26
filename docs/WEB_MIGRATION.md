# v0.2.0: Migrating from Streamlit to FastAPI + Jinja2 + HTMX + Tailwind

## Why

Streamlit is a fast way to build an internal tool, but it isn't a
general-purpose web framework: routing, per-request control, custom
HTML/CSS, and reuse from a non-Streamlit frontend (a future Tauri
desktop shell, a future public API) are all awkward-to-impossible in
it. This migration moves the presentation layer to a stack that
supports all of those, while changing nothing about how
recommendations are produced.

## What Phase 1 is (and isn't)

Phase 1 is infrastructure only:

- A working FastAPI app, structured for growth (see layout below)
- Jinja2 templating with a real base layout + nav + footer, not a
  single monolithic template
- Tailwind CSS via its CLI (a real production build — scans the actual
  templates and outputs only the classes in use — not the Tailwind CDN
  script, which Tailwind's own docs say isn't for production)
- HTMX vendored from npm into static files (not a CDN `<script>` tag —
  a future offline-capable desktop shell shouldn't depend on fetching
  a script from the internet at runtime)
- One placeholder route (`/`) that proves the whole chain works by
  calling `services.repository.count_journals()` — a real backend
  call, not static HTML, and rendering the real result (verified: shows
  the actual "55,745 journals" from the real database)

Phase 1 does NOT touch:

- The recommendation engine, scoring, or explanations
- The search page, filters, or export functionality — all of that is
  still Streamlit-only for now
- Any `services/`, `models/`, `importers/`, or `utils/` file — the
  whole point is that this layer didn't need to change at all

The Streamlit app (`app/`) keeps running exactly as it did before this
milestone. Both apps read from the same database and the same
`services/` layer; nothing about running one affects the other.

## Directory layout

```
web/                        FastAPI app (new — parallel to app/, which is Streamlit's)
    main.py                 App instance: settings, static mount, routers
    config.py                Settings (env-driven, JI_ prefix)
    templating.py             Shared Jinja2Templates instance + globals
    routers/
        home.py               Placeholder homepage route
    templates/
        base.html             Layout: <head>, nav, <main> block, footer
        partials/
            nav.html
            footer.html
        pages/
            home.html          Extends base.html
    static/
        src/
            input.css          Tailwind source (@tailwind directives)
        css/
            output.css         Built by `npm run build:css` (committed)
        js/
            htmx.min.js        Vendored from the htmx.org npm package
        img/                    (empty, reserved)
```

Why `web/` and not `app/` (the more common FastAPI convention): `app/`
was already taken by the Streamlit application before this milestone
started, and Phase 1's explicit instruction was to leave it untouched.
Reusing the name would have meant either colliding with it or renaming
the Streamlit app mid-migration — neither was in scope here.

## Why this supports the stated long-term plans

- **Tauri desktop app later**: `web/main.py` imports `services.*`
  exactly the way `app/pages/1_Submission_Search.py` does. A Tauri
  shell wrapping a local FastAPI server (or, further out, calling the
  same `services` functions directly from a Rust/Python bridge)
  doesn't require touching the business logic layer either way.
- **Future public API**: nothing in `web/routers/home.py` is
  page-specific in a way that would block adding `web/api/` alongside
  `web/routers/` later for a versioned JSON API, sharing the same
  `services` calls.
- **Auth, multiple pages, multilingual support**: none of these were
  built now (explicitly out of scope for Phase 1), but the router-per-
  concern structure and a single shared `templates` instance are the
  normal place to add them — an `web/routers/auth.py`, more files under
  `web/templates/pages/`, or Jinja2's own i18n extension later, without
  restructuring what's here.

## New dependencies

Python (added to `requirements.txt`, coexisting with Streamlit's):
`fastapi`, `uvicorn[standard]`, `jinja2` (already a transitive
Streamlit dependency, now a direct one too since `web/` imports it
directly), `python-multipart` (needed once forms/file uploads are
migrated), `pydantic-settings`.

Node (new `package.json`, dev-tooling only — not a runtime dependency
of the deployed app): `tailwindcss` (build-time only), `htmx.org`
(its built file is copied into `web/static/js/`, not imported at
runtime via Node).

## Running it

```
uvicorn web.main:app --reload
```

from the project root. See the README for the full instructions,
including rebuilding the CSS after a template's classes change.
