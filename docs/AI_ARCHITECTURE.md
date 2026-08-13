# Scilene AI: Architecture & Local Model Strategy (Design)

**Status:** Design only (#106). No real model is selected, downloaded,
or called anywhere in the codebase yet — see "Current implementation
state" at the end for exactly what exists today and what this
document only plans for.

---

## Core philosophy

Scilene must always work without AI. The recommendation engine stays:

- Offline-first
- Transparent
- Deterministic
- Explainable
- Reproducible

AI never determines which journals are recommended — it's an
optional assistant that improves the user's *input* before it reaches
the recommendation engine (`services/recommender.py`), not a
participant in ranking. Concretely, AI's possible roles are limited to
things like: improving a research idea into a title/abstract,
detecting research disciplines, expanding keywords, improving search
queries, or rewriting an explanation in more natural language. The
final journal ranking always comes from Scilene's own algorithm.

```
Recommendation Engine (deterministic)
        │
        ▼
AI Layer (optional)
        │
        ▼
Input Enrichment Only
```

AI must never directly modify journal ranking, matching score, or the
recommendation algorithm itself. This is the same boundary
`docs/RESEARCH_INTERPRETER.md` and `docs/ENRICHMENT.md` already draw
for their own optional layers — this document is the umbrella
philosophy those two implement pieces of.

---

## Installation philosophy (desktop)

The desktop installer should stay lightweight (~100 MB) and everything
should work immediately without AI. Only when a user first attempts an
AI-assisted feature (Improve Title, Generate Abstract, Detect
Discipline, ...) does Scilene explain:

> "Scilene AI is an optional component that enhances selected
> features. Your journal recommendations already work without AI."

If the user agrees: request permission → download Scilene AI → install
automatically → ready to use. This keeps the base install small and
respects users with limited bandwidth/storage — the same "never imply
the web version is intentionally limited, be honest about why desktop
offers more" spirit as `docs/DECISIONS.md`'s Decision #002 (Web vs.
Desktop roles).

## User experience

Users should never need to know GGUF, Ollama, llama.cpp, model names,
or inference runtimes — those are implementation details. The
application just presents "Enable Scilene AI"; the underlying model
stays hidden.

---

## Candidate models (evaluation only — no decision made)

| Candidate | Notes |
|---|---|
| Qwen 3 1.7B Instruct (Non-Thinking) | Strong multilingual (Arabic, Indonesian), good structured JSON output, small download, Apache 2.0 |
| Gemma 3 1B | Very lightweight, strong on-device optimization, broad multilingual support |

The final model should be selected only after benchmarking against
Scilene's own real-world tasks, not a public leaderboard score.

## Evaluation benchmark

A Scilene-specific benchmark (not a public leaderboard) covering:
discipline extraction, keyword expansion, title improvement, abstract
improvement, with English, Arabic, and Indonesian examples in each
category. The chosen model should be the one that performs best on
Scilene's actual workflow. This is a distinct, smaller benchmark than
`docs/BENCHMARK.md`'s recommendation-quality benchmark (Recall@K/MRR
against real published papers) — that one measures the deterministic
engine; this one measures a candidate AI model's task performance
before it's ever wired into the app.

---

## Reliability

AI responses must never be trusted blindly:

```
Generate JSON → Validate Schema
                      │
              ┌───────┴───────┐
              ▼               ▼
            valid           invalid
              │               │
              │          Retry once
              │               │
              │        ┌──────┴──────┐
              │        ▼             ▼
              │      valid       still invalid
              │        │               │
              ▼        ▼               ▼
         use result  use result   gracefully disable
                                  the AI result, continue
                                  without AI assistance
```

An AI failure must never interrupt the application — this is the exact
same rule `services/online_enrichment.py` already implements for
OpenAlex/Crossref (every failure mode collapses to `None`, never an
exception the caller has to special-case) and
`services/research_interpreter.py`'s placeholder is designed to keep
once real suggestions replace the hardcoded ones.

## Deterministic behavior

Where the runtime supports it: temperature 0 (or as low as practical)
and a fixed random seed, so the same input produces consistent results
whenever feasible — AI-assisted, not AI-random.

---

## Future-proofing: one internal interface

The application should expose one internal interface — a `AIProvider`
abstraction (#88, `services/ai_provider.py`) — so the underlying model
can be upgraded later without changing the user experience. Users only
ever interact with "Scilene AI"; the implementation behind that name
can evolve freely.

### Provider request/response contract (#87)

Every concrete provider — local or cloud — speaks the same wire
contract, which is what makes "local and cloud AI interchangeable"
concretely true rather than aspirational. A cloud provider
(`CloudAIProvider`) makes this an HTTP call; a local provider would
implement the identical shape however it talks to its runtime
(subprocess, local socket, in-process call):

```
request  -> {"task": "suggest_concepts" | "detect_disciplines" | "generate_search_inputs",
             "input": {...task-specific fields...}}

response <- {"ok": true | false, "data": {...} | null,
             "confidence": 0.0-1.0 | null, "error": string | null}
```

The response shape is `AIResponse` itself (`services/ai_provider.py`)
serialized as JSON — a provider that returns exactly this is
automatically interchangeable with every other provider, since nothing
downstream of `AIProvider` ever branches on which one answered.

`CloudAIProvider` is a real, working HTTP client against this contract
(verified in `tests/test_ai_provider.py` against a real local server,
including the failure path) — not wired to a specific paid vendor,
since this project has no API key or hosting budget to commit to one.
Pointing it at a real service that implements the contract is a
configuration change (`endpoint_url`, `api_key`), not a code change.

## Naming

Working name: **Scilene AI**. The public-facing name should be
revisited before release — "Scilene Assistant" or similar may better
reflect that AI assists researchers rather than replacing their
judgment (matches `docs/DESIGN_SYSTEM.md`'s Brand Philosophy: "guidance,
not automation").

---

## Open questions (unresolved — need a real decision before implementation)

- Which local inference runtime best fits Scilene?
- Should the AI runtime be bundled or downloaded separately?
- Which model gives the best multilingual quality for the smallest footprint?
- What's the acceptable download size?
- How should future model upgrades be delivered?

---

## Current implementation state

Done (scaffolding only, no real model anywhere):

- The core philosophy's boundary — AI enriches input, never ranks — is
  already enforced by construction in two places:
  `services/research_interpreter.py` (abstract → suggested concepts,
  see `docs/RESEARCH_INTERPRETER.md`) and
  `services/online_enrichment.py` (OpenAlex/Crossref, see
  `docs/ENRICHMENT.md`). Neither is imported by
  `services/recommender.py`, and both degrade every failure mode to
  "just don't show the enrichment" rather than an error.
- `services/ai_provider.py` (#88) — the `AIProvider` interface this
  document's "Future-proofing" section asks for, plus two concrete
  providers: `PlaceholderProvider` (wraps the existing hardcoded
  research_interpreter.py logic) and `CloudAIProvider` (#87 — a real
  HTTP client against the request/response contract above, not
  pointed at any actual paid vendor). No local-model provider yet.
- `services/discipline_detection.py` (#102) — "Detected Research
  Areas" after a search, letting a user refine recommendations with
  selected disciplines. Deliberately real and deterministic rather
  than a fake AI call: subject-tag frequency across the top results,
  reusing `journals.subjects` (already imported from DOAJ/SCImago)
  rather than a new taxonomy or hardcoded placeholder — directly
  matches #102's own "reuse existing metadata, avoid new taxonomies"
  guidance. A future real classifier could replace this without
  changing anything that calls `detect_disciplines()`. The "Edit"
  step (#102's own spec: "Remove incorrect disciplines, Add missing
  disciplines, Adjust the detected research focus") is now complete —
  checkboxes cover remove/select, and a plain text field
  (`extra_disciplines` on `POST /search/refine-with-disciplines`,
  comma/semicolon-parsed) covers "add missing." Originally only the
  checkboxes shipped; the add-missing half was caught in a later audit
  pass.
- Research Idea Assistant (#85, `web/routers/research_idea.py`) — the
  full "describe your idea" → generate → review/edit → "Continue to
  Search" flow, feeding `session["confirmed_tags"]` — the exact
  tag-based path a manual search already uses. Originally a popup
  modal reachable from the homepage; #143 relocated it to an inline,
  optional disclosure directly on `/search?mode=idea` instead (the
  homepage's "I only have a research idea" button links straight
  there now), since a modal read as a second, separate flow rather
  than "the same search page" the rest of this doc describes.
  `PlaceholderProvider.generate_search_inputs()` deliberately does NOT
  write new prose — writing a plausible title/abstract from a one-line
  idea is genuine text generation, which needs a real model to do
  honestly. It only restructures the researcher's own words (title =
  first sentence, abstract = the idea verbatim, keywords =
  stopword-filtered significant words, capped at 15) — a real
  generative provider would override this method without any
  web-layer change. `get_default_provider()` is the one place a future
  settings-driven provider choice would plug in.

  **Issue-priority correction:** #85's original design also called for
  a "suggested abstract" pre-filling the search page's abstract field.
  #110 (implemented after #85, and the actual current shape of the
  Submission Search page) explicitly says a user without an abstract
  should "provide at least `MIN_FALLBACK_TAGS` descriptive tags
  (`web/search_presentation.py`, 5 as of #143)... No abstract
  generation is required" — a direct contradiction. Per this project's
  rule for contradicting issues (newer wins), the web layer only ever
  reads `keywords` from `generate_search_inputs()`'s response;
  `title`/`abstract` are computed (the interface still returns them,
  since a different future consumer legitimately might want them) but
  never surfaced or carried into a search. There is no
  `prefill_abstract` session field or abstract-textarea pre-fill
  anymore — that mechanism was built, then removed once the
  contradiction was caught.

Not done:

- No model selected, benchmarked, downloaded, or called anywhere.
- No installer/download workflow (there's no desktop app to install
  into yet — see `docs/ARCHITECTURE_DECISIONS.md`).
- No JSON schema validation/retry pipeline for real AI output (nothing
  produces real AI output yet).
- The Scilene AI benchmark dataset (distinct from `docs/BENCHMARK.md`'s
  recommendation-quality benchmark).
- The public-facing name decision.

---

**Document Version:** 0.1

**Last Updated:** August 2026

**Status:** Approved (design) — implementation not started
