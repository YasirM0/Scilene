# Recommendation engine: scoring, strategies, prestige, confidence

This documents what `services/recommender.py` actually does — not the
long-term vision, just the current, real behavior. Code is the source
of truth; if this drifts from `recommend()`, trust the code.

## Candidate search

Before scoring, candidates are pulled from the database by keyword
(title/subjects/keywords columns, substring match), then narrowed by
any language/free-only/indexing/quartile/SINTA-level/review-time
filters. If the person left the keyword field blank, keywords are
derived from the paper title + abstract instead (as of v0.2.5, the web
UI never sends a title — see `docs/RESEARCH_INTERPRETER.md` — so in
practice this now derives from the abstract alone; the fallback logic
itself is unchanged) — stopwords removed
(see `services/stopwords.py`), words over 3 characters, de-duplicated,
capped at 15. This is still plain substring word extraction, not NLP or
embeddings.

## Scoring (v0.1.8: IDF-weighted, false-positive reduction)

Every candidate starts at score 0. For each keyword, points are added
per field it appears in:

| Field | Base points |
|---|---|
| Title contains the keyword | 5 |
| Subjects contains the keyword | 4 |
| Keywords field contains the keyword | 2 |

**Each keyword's points are multiplied by an IDF-style weight** based on
how many journals in the WHOLE database (not just this search's
candidates) contain that word — measured live via
`repository.keyword_document_frequency()`, not a hardcoded "generic
words" list. A word like "medicine" that appears in thousands of
journals contributes far less than a distinctive word like
"blockchain" that appears in a few dozen. Calibrated against real data:
`multiplier = clamp(log10((N+1)/(df+1)) / 1.7, 0.4, 2.2)`.

**A journal is dropped (not just low-scored) if:** its score is 0, OR
it only matched via the weakest field (the keywords column) with fewer
than 2 distinct keywords — a single generic word hit in the
lowest-authority field is exactly the pattern that used to surface
irrelevant journals (e.g. a medical journal for a policy manuscript via
one coincidental keyword-field overlap).

## Strategies

Three strategies exist, all backed by real database columns. There is
no "Best Match" (would need semantic/embedding similarity) and no
"Beginner Friendly" (would need an acceptance rate) — deliberately left
out rather than faked. Review time is NOT a ranking strategy (see
"Review time" below) — it's a search filter instead.

**Balanced (default)** — sorts by weighted `score`, +2 bonus for free.

**Lowest APC** — free first, then ascending confirmed USD amount
(unconfirmed sorts last), `score` as tiebreak.

**Highest Prestige** — sorts by the journal's best quartile across all
confirmed sources (Q1 > Q2 > Q3 > Q4 > untiered), then SJR, then
`score`. Journals with no quartile (most DOAJ-only journals) rank at
the bottom regardless of topical score.

## APC / budget handling

`apc_amount` is free text (e.g. `"40 USD"`, `"40 USD; 450000 IDR"`).
Only an explicit USD figure is trusted; no currency conversion is
guessed. A paid journal with no parseable USD amount is excluded from
budget-limited searches rather than assumed to fit.

## Review time

A search filter (`max_review_weeks`), not a ranking strategy — pushed
into SQL directly since `review_weeks` is a clean, fully-populated
integer column. Deliberately excluded from strategy sorting: mixing
speed into a relevance/prestige ranking implies a tradeoff the person
didn't necessarily ask for, whereas a filter lets them set their own
ceiling independently of everything else.

## Confidence levels

Each result gets a label — Excellent / Strong / Moderate / Weak / Poor
— from TWO things that must both hold for the top two tiers:

1. **Rank** — which fifth of this search's own results it falls in.
2. **A floor** — its `normalized_score` must be at least the larger of
   a small absolute floor (0.05) and 45% of this search's own TOP
   result's normalized_score.

The floor is deliberately RELATIVE to this search's own best result,
not one fixed number for every search (that was v0.1.8's first attempt,
and it was miscalibrated — see "Recalibration" below). A search with
many fallback keywords has a structurally lower achievable ceiling than
a precise 2-keyword search, so comparing every search against the same
fixed number punished the former unfairly.

This is still NOT a calibrated probability of fit or acceptance — no
outcome data backs it — and the search page's help text says so.

### Recalibration (post-launch fix)

The first version of this used a single fixed floor (0.12) and a
looser inclusion rule (any title/subject hit, or 2+ keyword-field hits,
was enough to include a journal at all). Two real problems came out of
testing at scale:

1. **Too conservative for typical manuscripts.** A diffuse manuscript
   (title+abstract fallback, up to 15 keywords) produces a huge OR-based
   candidate pool — thousands of journals matching on just one fairly
   common word. That diluted the percentile ranking so badly that the
   "top 40% by rank" often sat at a normalized_score around 0.02 — far
   below the fixed 0.12 floor — so almost everything got capped at
   Moderate and hidden by default (one real test: 17 of 1,274 results
   visible).
2. **Fixed thresholds don't transfer across searches with very
   different keyword counts** — the root cause of #1.

Fix, in two parts:
- **Inclusion now scales with keyword count**: `min_required_hits = 1`
  when there are ≤3 keywords (an explicit, precise search), otherwise
  `max(2, ceil(0.2 × keyword_count))`. This shrinks the noisy long tail
  at the source instead of just hiding more of the output afterward —
  one real test went from 8,066 diluted candidates to 735 meaningful
  ones for the same manuscript.
- **The floor became relative** (45% of this search's own top score,
  floored at 0.05) instead of one fixed number. Verified against a
  deliberately adversarial case — "Coral Reef Bleaching" — where
  several textile-industry journals matched only via the ambiguous word
  "bleaching" (a real textile process term) and, under the old fixed
  floor, got mislabeled Excellent/Strong alongside the genuinely correct
  match ("Coral Reefs"). The relative floor correctly separates them:
  "Coral Reefs" scored 0.308 normalized, the textile false-positives
  all tied at 0.117 — well below 45% of 0.308 (0.139) — so only the
  genuine match now shows as Excellent.
- Net effect on the earlier diffuse-manuscript case: 58 Excellent
  results shown by default (was 17), with zero medical/engineering
  journals in the top 30 (checked directly, not assumed).

## "Why this journal?" explanations

Template-based natural-language sentences (`services/explain.py`), not
an LLM — out of scope for this milestone. Built from which of the
manuscript's own terms matched in which field:

- Subject matches → "covers X, Y, and Z, matching your manuscript's
  subject area"
- Title matches → "its own title reflects X and Y"
- Keyword-field-only matches (weakest signal, shown only if nothing
  stronger matched) → "is tagged with X, related to your manuscript"

Deliberately does NOT mention APC, indexing, language, country, or
review time — those already have their own place on the card, and
repeating them here would be redundant, not explanatory.

## Future recommendations (out of scope for v0.1.8)

Flagged rather than built, per this milestone's own scope boundary:

- **TF-IDF or embedding-based similarity** for "Best Match" — the
  natural next step for recommendation quality beyond keyword+IDF
  scoring, but it's a genuinely different technique (vector similarity,
  a model or index to maintain) rather than a tuning pass on the
  current approach, so it belongs in its own milestone.
- **A real "Beginner Friendly" strategy** — needs an acceptance-rate or
  difficulty signal that doesn't exist in any imported dataset yet.
- **Per-field keyword weighting profiles** (e.g. detecting "this looks
  like a policy manuscript" and re-weighting subject categories
  accordingly) — plausible without ML, but a meaningfully separate
  feature (a classifier or rule table over subject taxonomies) rather
  than a scoring tweak.
- **Persisting `keyword_document_frequency` results** (a small cache
  table instead of a live COUNT query per keyword per search) if
  search latency becomes noticeable as the database grows further.