# Query Normalization & AI-Assisted Search Pipeline (Design)

**Status:** Design only, mapped honestly against what's actually built
today. This document defines the pipeline #109 asks for and shows
which stages already have a real, deterministic implementation, which
are genuinely unimplemented, and — critically — why none of that
changes what `services/recommender.py` does.

---

## Core rule (restated from `docs/AI_ARCHITECTURE.md`)

Scilene AI prepares a search query. It never ranks journals. Every
stage below produces plain data — normalized text, a list of keyword
strings, a language name — that flows into the exact same `recommend()`
parameters a manually-typed search already uses. There is no second,
AI-influenced scoring path.

---

## The pipeline, stage by stage

```
User Input (title / abstract / manual tags)
        │
        ▼
Language Detection ───────── services/language_detection.py (#89, REAL)
        │
        ▼
Translation ───────────────── NOT IMPLEMENTED (see below)
        │
        ▼
Query Normalization ───────── partial: services/recommender.py's own
        │                     fallback tokenizer (lowercase, split,
        │                     stopword-filter) — not a dedicated stage
        ▼
Keyword Expansion ─────────── NOT IMPLEMENTED (see below)
        │
        ▼
Discipline Detection ───────── services/discipline_detection.py (#102, REAL)
        │                      but runs AFTER a search, not before it
        ▼
Canonical Search Representation ── NOT a formal object today (see below)
        │
        ▼
services.recommender.JournalRecommender.recommend()  (UNCHANGED, deterministic)
```

### Language Detection — real, but scoped narrower than this pipeline implies

`services/language_detection.py` (#89) really does run `langdetect`
(seeded, deterministic) on the pasted abstract. But today its ONLY
effect is pre-checking a box in the **journal language filter** (which
languages a journal accepts manuscripts in) — see
`web/language_presentation.py`. It does not currently feed a
translation step or influence the search keywords themselves. This
document treats that as the first honest gap: the pipeline diagram
above implies detection feeds translation; today it feeds a filter
instead. Both are legitimate uses of the same detection call, and nothing
prevents wiring it into translation later — but it isn't today.

### Translation — not implemented

No translation of any kind exists in this codebase. Building it
honestly requires either a real translation model/API (a genuine
AI dependency, not something to fake with a dictionary) or accepting
that non-English abstracts are only matched via whatever English
loanwords/technical terms happen to overlap with journal metadata —
which is exactly what happens today, silently, as a side effect of
`recommend()`'s plain substring matching. See "AI fallback behavior"
below for why that silent behavior is actually the correct fallback,
not a bug to hide.

### Query Normalization — partial, informal

`services/recommender.py`'s fallback path (used when no keywords are
confirmed) already does a crude normalization: lowercase, strip
punctuation, split on whitespace, drop words ≤3 characters, remove
stopwords (`filter_stopwords`). That's real code, but it's not a
distinct, reusable "normalize this query" stage — it's inlined into
the recommender's own candidate-keyword construction. A dedicated
normalization stage (terminology normalization, e.g. "ML" →
"machine learning") is not implemented; there's no synonym or
terminology-mapping data source for it today.

### Keyword Expansion — not implemented

No synonym or concept-expansion logic exists. The natural extension
point, if this is built later, is `AIProvider.generate_search_inputs()`
or a new `AIProvider.expand_keywords()` method (`services/ai_provider.py`,
#88/#87) — a provider call whose *output* (more keyword strings) would
be reviewed/editable by the user before it ever reaches
`confirmed_tags`, exactly like Research Interpreter suggestions today
(`docs/RESEARCH_INTERPRETER.md`). Not built in this pass: there's no
real expansion source (dictionary or model) to call yet, and a
hardcoded placeholder wouldn't demonstrate real value any more than
one would for #85's idea-to-abstract generation.

### Discipline Detection — real, but positioned differently than this pipeline implies

`services/discipline_detection.py` (#102) is real and deterministic:
subject-tag frequency analysis across the top current results. But it
runs **after** a search already executed, as a refinement step ("Detected
Research Areas" → re-run with selected disciplines added to
`confirmed_tags`) — not before the first search, as this pipeline's
diagram would suggest. This is a deliberate, documented choice from
#102's own implementation: it needs *results* to analyze, so it can't
run before the first search exists. A true pre-search discipline
prediction (classifying the abstract itself, before any candidates are
fetched) is a different, unimplemented capability.

---

## Canonical Search Representation

The issue asks for one canonical internal shape passed to the
recommendation engine, carrying both the original input and any
normalized/expanded/translated version of it. Today, `recommend()`'s
own parameter list — `title`, `keywords`, `abstract`, `languages` — IS
that representation; there's no separate object wrapping them. This
document formalizes what each parameter carries and where it comes
from, since #109's acceptance criteria calls for that formalization
even though no field types are changing:

| Field | Carries | Populated by (today) |
|---|---|---|
| `title` | The user's own paper title, verbatim | manual input only |
| `abstract` | The user's pasted abstract, verbatim (never translated today) | manual input only |
| `keywords` | Confirmed concepts: accepted Research Interpreter suggestions + manually-typed/idea-mode tags, **indistinguishably** | `session["confirmed_tags"]` (`web/routers/search.py`) |
| `languages` | Journal-language filter selection, pre-checked from detected abstract language | `web/language_presentation.py` (#89) |

If translation, expansion, or pre-search discipline detection are
built later, their output lands in exactly these same fields —
expanded/translated text becomes more `keywords` entries or a modified
`abstract`, never a new parameter recommend() has to special-case.
This is the same "one list, one code path" principle
`docs/RESEARCH_INTERPRETER.md` already documents for accepted
suggestions vs. manually-typed tags — extended here to the whole
pipeline rather than just the tag field.

**Original input is never discarded.** `title` and `abstract` are
always passed through unmodified alongside `keywords` — a translated
or expanded version, if one existed, would be an *addition* to
`keywords`/an separate normalized field, not a replacement of what the
user actually wrote. Nothing in the current code violates this (there's
no destructive normalization anywhere today), but it's worth stating as
a constraint for whatever gets built next.

---

## Multilingual support strategy

1. **Journal-side language matching** is real today (#89): the search
   filter matches confirmed languages against a journal's accepted
   manuscript languages, and a query pasted in a supported language
   pre-checks that filter automatically.
2. **Query-side translation** is not built. When it is, it should be
   an `AIProvider` call (`generate_search_inputs` or a dedicated
   `translate` method) whose output is reviewed by the user (matching
   `docs/RESEARCH_INTERPRETER.md`'s "accept/edit" pattern) before
   becoming part of `keywords`/`abstract` — never applied silently.
3. **Without translation**, a non-English abstract still searches via
   whatever terms overlap with journal metadata (titles, subjects,
   and — as of #100 — alias titles in other languages, which do
   sometimes let a non-English query match through
   `journal_aliases`). This is a real, if limited, fallback — not
   nothing.

## AI fallback behavior

If no `AIProvider` is configured/reachable (today: always, since no
concrete provider is wired into search), every stage above marked
"NOT IMPLEMENTED" simply doesn't run. Nothing blocks or degrades: the
user's title/abstract/manual tags reach `recommend()` exactly as
typed, through the same fallback tokenizer that's always been there.
This mirrors the existing rule in `docs/AI_ARCHITECTURE.md`
("Deterministic behavior" — search must always work without AI) and
`docs/ENRICHMENT.md` (online enrichment failures degrade to "don't
show it," never an error).

## Deterministic behavior when AI is disabled

Identical to "AI fallback behavior" above by construction, since
nothing in the current pipeline is conditioned on an AI call
succeeding — every real stage today (`language_detection.py`,
`discipline_detection.py`) is already itself deterministic (seeded
`langdetect`, frequency counting), not an LLM call with a possible
failure mode. The distinction between "AI disabled" and "AI stage not
built yet" is currently moot: there is no AI stage in this pipeline
today that isn't also fully deterministic.

## Fairness philosophy

Two researchers describing the same work should receive comparable
recommendations regardless of language, terminology choice, or
abstract quality — the query-normalization pipeline exists to narrow
that gap, not to replace researcher judgment (`docs/DESIGN_SYSTEM.md`'s
"guidance, not automation"). Concretely, today: the language filter's
auto-detection (#89) removes one piece of friction for non-English
speakers without requiring them to know Scilene's UI terminology, and
the fallback stopword-filtered tokenizer treats a full abstract and a
short list of manual tags through the same scoring path — a
sparse/weak abstract doesn't get a *worse* code path, only fewer
extracted keywords to match against. Translation and expansion, once
built, extend this same goal; they do not introduce a new one.

## AI never influences ranking directly

Restated precisely for this pipeline: every stage's output — detected
language, normalized keywords, expanded keywords, detected disciplines
— becomes plain entries in `keywords`/`abstract`/`languages`, the same
parameters a manually-typed search already populates.
`services/recommender.py`'s scoring loop (`services/recommender.py`,
keyword/title/subject weight computation) has no branch, flag, or
parameter that distinguishes "this keyword came from AI" from "this
keyword was typed by hand." This isolation is enforced the same way
`docs/ENRICHMENT.md` and `docs/RESEARCH_INTERPRETER.md` already enforce
it for their own features — not a new mechanism invented for this
document, the same one applied consistently.

---

## Relationship to other design docs

- `docs/AI_ARCHITECTURE.md` — the `AIProvider` interface and contract
  this pipeline's unimplemented stages would call into.
- `docs/RESEARCH_INTERPRETER.md` — the accept/edit/cycle UI pattern any
  future translation or expansion suggestion should reuse, per the
  "user always reviews AI output" rule.
- `docs/BENCHMARK.md` / `benchmark/` (#112) — the tool that would
  measure whether a real normalization/expansion stage actually
  improves Recall@k/MRR before it's adopted, per that document's own
  stated purpose ("replace intuition with measurable evidence").
