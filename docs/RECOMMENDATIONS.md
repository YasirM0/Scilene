# Recommendation engine: scoring, strategies, prestige, confidence

This documents what `services/recommender.py` actually does — not the
long-term vision, just the current, real behavior. Code is the source
of truth; if this drifts from `recommend()`, trust the code.

## Candidate search

Before scoring, candidates are pulled from the database by keyword
(title/subjects/keywords columns, substring match), then narrowed by
any language/free-only/indexing/quartile/SINTA-level/review-time
filters. If the person left the keyword field blank, keywords are
derived from the paper title + abstract instead — stopwords removed
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
2. **An absolute floor** — its `normalized_score` (score ÷ its own
   theoretical max, assuming every keyword hit all 3 fields) must be
   at least 0.12.

The floor exists because rank alone is fooled by a weak search: if
every candidate is a mediocre match, the best of that bunch would still
look "Excellent" purely by comparison. The 0.12 threshold is calibrated
against real measurements, not guessed — even a near-perfect match (a
journal literally titled "Blockchain" for a "blockchain governance
digital" query) only reached ~0.33 normalized score, since it's rare
for every keyword to hit all 3 fields; genuine noise matches (a single
coincidental word overlap) measured around 0.01. 0.12 sits well above
the noise floor while staying reachable by real topical matches.

This is still NOT a calibrated probability of fit or acceptance —
there's no outcome data behind it, and the search page's help text
says so explicitly.

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