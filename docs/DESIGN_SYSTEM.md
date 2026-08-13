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

# Name & Logo

"Scilene" combines **Sci** (science) with **Selene**, the Greek
personification of the moon. The moon has long served as a natural
guide for navigation and exploration — Scilene aims to guide
researchers through an increasingly complex scholarly landscape the
same way, toward the right journals, literature, and decisions.

The logo (`web/static/img/scilene-logo.png`) traces the letter "S"
through a subtle, abstract crescent — meant to suggest an orbit or
research journey rather than a literal moon — with a small gold star
standing in for a guiding star (discovery, direction, confidence).
This is also where the brand colors below come from directly: navy
for the night sky, trust, and academia; gold for discovery, insight,
and progress.

This is the project's actual design rationale, not marketing framing
— see the About page (`web/templates/pages/about.html`) for the
user-facing version of the same explanation.

---

# Brand Colors

Defined in `tailwind.config.js` under `theme.extend.colors`, used as
Tailwind utility classes (`bg-navy-600`, `text-horizon-600`, etc.).
Finalized in v0.2.5 (Issue 4) — supersedes an earlier, provisional
horizon-as-primary scheme this document described before the brand
identity was settled.

| Token | Base hex | Role |
|-------|----------|------|
| `navy` | `#1E3A5F` (Navigation Navy) | **Primary.** Logo, primary buttons, navigation bar, headings, icons, links, major interface elements. Night sky, trust, stability, academic credibility. |
| `horizon` | `#2F5E88` (Horizon Blue) | **Secondary.** Hover states, secondary buttons, interactive highlights, focus rings — not the default resting color for links/buttons, the state they change *to*. |
| `gold` | `#C9A227` (Guiding Gold) | **Accent — used sparingly (~5-10% of the interface).** The guiding star in the logo; Excellent-tier recommendation badges; small highlights. Never a primary interface color. |

Target balance across the interface: ~80% neutral (white/gray
backgrounds), ~15% navy, ~5% gold — horizon is a state, not a
resting-state budget line. Concretely: a link is navy by default and
turns horizon on hover, not horizon by default.

Each color needs more than its base hex because Tailwind utilities
reference specific shades (`horizon-50`, `horizon-500`, `horizon-600`,
`horizon-700`, ...). Shades other than the base are derived
mechanically, not hand-picked, so they stay reproducible:

- **Lighter shade** (e.g. `-50`, `-500`): mix the base RGB with white.
- **Darker shade** (e.g. `-700`, used for `:hover` states): multiply
  each RGB channel by `0.8`.
- **`navy-300`** is the one hand-picked exception, not derived by that
  formula — it exists specifically for dark-mode heading/link text.
  `navy-600` (correct on a white background) is nearly illegible on a
  dark surface, so dark mode swaps to this lighter tint instead. Solid
  navy-filled buttons are unaffected (white text on top reads fine in
  either theme) and stay `navy-600` in both.

This is a starting scale, not a final one — if a designer produces a
full hand-tuned palette later, replace these derived values directly
in `tailwind.config.js`; nothing downstream depends on how the shades
were computed, only on the class names.

## Dark mode

Dark is the default appearance; light is an explicit, remembered
opt-out (`localStorage.theme`), toggled from the nav bar. Uses
Tailwind's `darkMode: "class"` — a `dark` class on `<html>`, added by
an inline script in `base.html`'s `<head>` that runs before first
paint (avoids a flash of the wrong theme, which a deferred script
can't do).

Dark-mode neutrals reuse Tailwind's own default gray-700/800/900
scale rather than a custom navy-tinted dark palette — simpler, safer,
and pairs fine with navy/horizon/gold as accents in either theme. The
navy nav bar is the one deliberate exception: it stays navy regardless
of theme (see the brand table above — "Navigation bar" is an explicit
navy use case, not something that should flip with the toggle).

## JavaScript exceptions

The app is server-rendered Jinja2 + HTMX with no custom JavaScript, by
default. Two narrow, deliberate exceptions exist, both because the
behavior they need is genuinely impossible in plain HTML/CSS, not
because reaching for JS was easier:

- **Dark-mode toggle** (`partials/nav.html`) — flips a `localStorage`-
  backed preference, which is inherently client-local browser state,
  not application data HTMX would ever need to know about.
- **Compact multi-select filters** (`static/js/multiselect.js`, #142)
  — chips-inside-a-collapsed-control with click-outside-to-close,
  matching the Streamlit `st.multiselect` behavior this replaced.
  Native `<details>/<summary>` (the original zero-JS attempt) has no
  "click outside to close" behavior at all, and nesting a removable
  chip inside a clickable `<summary>` makes removing a chip *also*
  toggle the dropdown as an unwanted side effect. See that file's
  header comment for the full reasoning.

Any future addition to this list should meet the same bar: the
behavior must be provably unavailable in HTML/CSS/HTMX alone, not
merely more convenient to build in JS.

## Confidence tier colors

`CONFIDENCE_COLORS` / `CONFIDENCE_STAR_COLORS` in `web/search_presentation.py`
map each recommendation confidence tier to the brand palette, matching
the finalized color philosophy directly: Excellent → gold, Strong →
navy, Moderate → horizon, Weak/Poor → neutral gray (only the first
three tiers have an assigned brand color). The star rating next to
each badge is colored the same as the badge text — previously always
plain gray-400 regardless of tier, which was both low-contrast and
disconnected from the badge beside it.

## Build note

`web/static/css/output.css` is a committed, pre-built Tailwind output
(see WEB_MIGRATION.md — this is intentional, not a checked-in
artifact by accident). Any change to `tailwind.config.js` or to which
utility classes templates use must be followed by
`npm run build:css` to keep it in sync.

---

# Typography

## Wordmark

"SCILENE" as set in the logo (`web/static/img/scilene-logo.png`) is a
fixed image asset, not a live web font — the wordmark's exact letterforms
aren't reproduced anywhere else in the interface. Body/UI text uses an
unrelated, ordinary typeface (below); this is deliberate, not an
oversight — a distinct display wordmark next to plain, highly legible
UI text is a common and appropriate split, and inventing a second
"brand" web font to match the logo would add a real asset-loading cost
for no functional benefit.

## Font choice

No custom web font is loaded. `base.html` uses Tailwind's default
system font stack (`ui-sans-serif, system-ui, -apple-system, ...`) —
each platform renders its own native UI font (San Francisco on Apple
platforms, Segoe UI on Windows, Roboto on Android, etc.). This is a
deliberate choice, not a placeholder:

- Zero font-loading latency or flash-of-unstyled-text — consistent
  with the project's offline-first, no-unnecessary-dependencies
  principles (`docs/ARCHITECTURE.md`).
- Every platform's native font is already tuned for that platform's
  screen rendering.
- "Timeless rather than trendy" (see Design Principles below) argues
  against chasing a fashionable webfont that will look dated in a few
  years.

## Spacing & hierarchy

Follows Tailwind's default type scale as used throughout the templates
— `text-xs`/`text-sm` for secondary/meta text, `text-base`/`text-lg`
for body copy, `text-2xl`–`text-5xl` for headings, with `font-medium`/
`font-semibold`/`font-bold` (not italics or letter-spacing tricks) as
the primary way to establish hierarchy. Headings use `navy-600` (see
Brand Colors above) rather than pure black, which is itself part of
the type hierarchy — it's what visually marks a heading as a heading
before the reader even parses the larger size.

---

# Design Principles

- **Minimalist** — no gradients, no decorative flourishes; every
  element on screen earns its place.
- **Flat** — solid fills only; no drop shadows or 3D effects standing
  in for hierarchy that spacing and color already provide.
- **Calm and trustworthy** — the interface should never feel like it's
  competing for attention. This is also why gold stays rare (~5-10% of
  the interface, see Brand Colors) — its scarcity is what makes it
  legible as "this matters" when it does appear.
- **Timeless rather than trendy** — avoid styling choices whose main
  appeal is that they look current right now.
- **Academic rather than corporate** — plain language, real citations,
  no marketing gloss.
- **Professional rather than flashy.**
- **Avoid AI clichés** — no glowing effects, neon colors, gradients, or
  futuristic styling anywhere in the interface, including any future
  AI-assisted features (see `docs/RESEARCH_INTERPRETER.md`). A
  suggested tag should look exactly like a normal tag, not like it
  came from a different, flashier product.

---

# Brand Philosophy

Scilene is about guidance, not automation. The interface should
inspire confidence rather than excitement — the tagline is "Navigate
Scholarly Publishing with Confidence," not "Discover journals
instantly" or similar. Every visual element should exist for a reason
traceable back to that idea (see Name & Logo above for where the
navy/gold/guiding-star motif actually comes from) — a component that's
only there to look impressive doesn't belong.

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
| `filter_panel.html` | The Advanced Mode filter form fields (indexing, quartile, SINTA level, language, budget). |
| `search_form.html` | Abstract input + Research Interpreter panel (manuscript mode only), and the Search Concepts tag builder (both modes) — see `docs/RESEARCH_INTERPRETER.md`. |
| `confirmed_tags.html` | Chip list of confirmed search concepts, individually removable. Supports an HTMX out-of-band render (`oob=True`) for routes that update it from elsewhere. |
| `search_history.html` | List of past searches from the session, each rerunnable. |
| `pagination.html` | Page-number controls for the results list. |
| `export_panel.html` | The row of export-format buttons (PDF/DOCX/XLSX/MD/CSV). |
| `accordion_card.html` | One expandable card for a `<details name="...">` group — same `name` on every card in a group makes them mutually exclusive natively, no JS. Used by the About page. |

## Shared card pattern

Several components (`journal_card`, `stat_card`, `feature_card`)
independently use the same base card styling:

```
bg-white rounded-lg border border-gray-200
```

This is a convention, not an enforced abstraction — new components
should match it for visual consistency, but it isn't worth wrapping in
its own macro at the current component count. Revisit if the card
pattern needs to change in more than one place at once.

---

**Document Version:** 0.2

**Last Updated:** August 2026

**Status:** Approved
