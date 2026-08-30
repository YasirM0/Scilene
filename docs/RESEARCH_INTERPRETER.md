# Research Interpreter

**Status:** "Key Research Focus" is real and interactive (accept/
suggest-another/edit) as of #113's follow-up (`services/focus_detection.py`
matches the abstract against `journals.keywords`, deterministic, not a
fake AI call). "Field of Study" (`services/field_detection.py`,
matching `journals.subjects` -- #53) was tried the same way and found
NOT accurate enough for that treatment: tested directly against a real
abstract about internet access and social stratification in Indonesia,
it suggested "Computer Science", then "Environmental Science", then
"Public Health" on retries. An embedding-similarity alternative was
tried too and didn't fix it either (ranked "Technology" above "Social
Sciences" for the same abstract). The underlying vocabulary is only
~20-44 broad category names, too coarse for a specific interdisciplinary
topic -- a structural limit, not a bug either technique fixes. So Field
of Study is now non-interactive "e.g." example text next to the tag
box (`services/research_interpreter.py::field_of_study_examples()`),
never presented as a detected/confident claim the way Key Research
Focus is. This document describes the architecture the interpreter
plugs into either way.

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
- **No abstract:** the user provides at least `MIN_FALLBACK_TAGS`
  (`web/search_presentation.py`, 5 as of #143) descriptive tags
  directly via the same Search Concepts tag builder described below —
  not a second, separate field. `/search?mode=idea` (the homepage's
  "I only have a research idea" button, and the Research Idea modal's
  "Continue to Search") renders this page with the abstract field and
  Research Interpreter panel omitted entirely, so that builder is the
  only thing shown (`web/templates/components/search_form.html`,
  `web/routers/search.py`'s `search_page()`). #143 replaced an earlier
  design with a SEPARATE "Don't have an abstract? Add tags instead"
  textarea alongside this same builder — two ways to add a tag on one
  page, with no stated relationship between them.

Both paths feed the exact same place: `session["confirmed_tags"]`
becomes the `keywords` list passed to
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
services/research_interpreter.py  (real focus-detection + example-text logic)
        │
        ▼
partials/interpreter_panel.html  (re-rendered, swapped back in)
```

This is why there's no custom JS file for this feature (see
`docs/DESIGN_SYSTEM.md`'s "JavaScript exceptions" note for the two
narrow, deliberate exceptions that do exist elsewhere in the app, and
why each was judged genuinely necessary rather than convenient). Two
things worth calling out as pure-HTMX
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

- Persisting interpreter state into search history (`rerun_history`
  restores past results/filters but not past suggestion state).
- A bulk paste-many-at-once entry for the no-abstract path — #143
  removed the old comma/semicolon-separated textarea in favor of the
  same one-at-a-time Search Concepts builder the abstract path already
  uses (see "Two search paths, one destination" above); pasting a
  comma-separated list into that input still only confirms it as one
  tag.
