# Research Interpreter (UI scaffolding)

**Status:** Interaction and UI only — `services/research_interpreter.py`
returns hardcoded placeholder suggestions. No real analysis of the
abstract happens yet. This document describes the architecture the
real interpreter will plug into, not a finished feature.

---

## What "Research Interpreter" means here

Earlier drafts of this feature framed it as "Scilene AI" suggesting
tags via some unspecified generative process. That framing was
deliberately dropped: the real interpreter is expected to be an
**embedding-based classifier**, not a generative/LLM-style model, so
nothing here assumes prompt construction, streaming tokens, or any
other LLM-specific shape. The UI-facing name is "Suggested by Scilene"
— not "Suggested by Scilene AI" — for the same reason: the UI
shouldn't care whether a suggestion came from an embedding model, a
future LLM, or (today) a hardcoded list.

The contract `services/research_interpreter.py` exposes is deliberately
narrow: abstract text in, a short list of `{category, label, value,
color}` concept suggestions out. Replacing the placeholder pool with a
real model later means changing the body of `suggest_concepts()` —
nothing that calls it, and nothing in the templates.

## Two search paths, one destination

- **Preferred:** paste an abstract → the interpreter suggests a Field
  of Study and a Key Research Focus, which the user accepts, cycles
  ("Suggest another"), edits inline ("✏ Edit" — #110, replaces the row
  with a plain text input; Save writes the typed text as that
  suggestion's value, same as if the pool had suggested it), or
  removes.
- **No abstract:** the user provides at least 10 descriptive tags
  directly (`fallback_tags` on the search form) instead.

Both paths feed the exact same place: `session["confirmed_tags"]` (plus
any parsed `fallback_tags`) becomes the `keywords` list passed to
`services.search_service.search_journals()` — the same parameter a
manually-typed keyword already used. The recommender has no concept of
"came from an abstract" vs. "came from a tag" — see
`web/routers/search.py`'s `run_search()`. This is what "the
recommendation engine receives normalized research concepts regardless
of origin" means concretely: one list, one code path, unchanged
`services/recommender.py`.

## Why HTMX, not a JavaScript state machine

The interaction (analyzing → reveal suggestions → accept/cycle/remove
→ detect abstract drift → confirm) is genuinely stateful, but the
state lives in the **session** (`web/session_store.py`, same place
search history and pagination already live), not in client-side
JavaScript. Every button is an HTMX request that mutates session state
server-side and re-renders a partial:

```
User Action (HTMX request)
        │
        ▼
web/routers/interpreter.py  (reads/writes session state)
        │
        ▼
services/research_interpreter.py  (placeholder suggestion logic)
        │
        ▼
partials/interpreter_panel.html  (re-rendered, swapped back in)
```

This is why there's no custom JS file for this feature (the one
exception in the whole app is the dark-mode toggle, which is
legitimately client-local browser state, not application data — see
`docs/DESIGN_SYSTEM.md`). Two things worth calling out as pure-HTMX
techniques rather than something needing hand-written JS:

- **The "analyzing" delay** is `hx-trigger="load delay:900ms"` on the
  analyzing message, auto-firing a follow-up `GET /search/interpret/reveal`
  once loaded — no `setTimeout`.
- **Updating two page regions from one response** (accepting a
  suggestion removes its card from the interpreter panel *and* adds a
  chip to the confirmed-tags list) uses an HTMX out-of-band swap
  (`hx-swap-oob="true"` on a second fragment in the same response) —
  see `components/confirmed_tags.html`'s `oob` parameter.

## Session state

Added to `web/session_store.py`'s per-session defaults:

- `interpreter_suggestions` — list of suggestions not yet accepted or
  removed.
- `interpreter_abstract_snapshot` — the abstract text suggestions were
  last generated from, used only to detect drift (comparing against
  `confirmed_tags` wouldn't work — that list changes for unrelated
  reasons too, like removing a manually-added tag).
- `confirmed_tags` — plain strings, indistinguishable regardless of
  whether they came from an accepted suggestion or a manually-typed
  tag. This is what actually reaches the recommender.

## Not implemented

- Any real analysis of the abstract — `suggest_concepts()` always
  returns the same two placeholder values on first call.
- Persisting interpreter state into search history (`rerun_history`
  restores past results/filters but not past suggestion state).
- A dedicated per-tag "add one tag at a time" UI for the fallback path
  — it's a single comma/semicolon-separated textarea, parsed the same
  way the old Keywords field was.
