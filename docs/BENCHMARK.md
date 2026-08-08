# Scilene Benchmark

This document defines how Scilene evaluates changes to its recommendation engine and AI components.

The purpose of the benchmark is to ensure every improvement is supported by evidence rather than intuition.

---

# Goals

The benchmark answers one question:

> Does this change genuinely improve Scilene's recommendations?

Any new embedding model, recommendation algorithm, AI-assisted enrichment process, or ranking change should be evaluated using this benchmark before being adopted.

---

# Principles

- Compare against evidence, not intuition.
- Always compare against a baseline.
- Test with real published research.
- Evaluate fairness across disciplines.
- Keep the benchmark reproducible.

---

# Benchmark Dataset

The benchmark dataset will consist of real published papers collected from OpenAlex.

Each benchmark record should contain:

- Abstract
- Journal
- Subject Area
- Category
- OpenAlex ID
- Publication year
- Author affiliation country (when available)

Only journals that exist inside Scilene's database should be included.

The dataset should be stratified across major disciplines.

---

# Evaluation Metrics

Primary metrics:

- Recall@5
- Recall@10
- Recall@20
- Mean Reciprocal Rank (MRR)

Secondary metrics:

- Subject Area match rate
- Category match rate

Future metrics:

- Fairness across languages
- Fairness across disciplines
- User validation scores

---

# Baselines

Every experiment should be compared against at least one baseline.

Initial baseline:

- TF-IDF / keyword matching

Future baselines may include:

- Previous embedding model
- Previous recommendation engine version

---

# Evaluation Process

1. Build benchmark dataset.
2. Run recommendation pipeline.
3. Record top recommendations.
4. Compute evaluation metrics.
5. Compare against baseline.
6. Document results.

---

# Version History

Each benchmark release should include:

- Dataset version
- Embedding model
- Recommendation engine version
- Benchmark metrics

This creates a permanent history of Scilene's improvements over time.

---

# Future Work

Potential future additions:

- Human evaluation
- Interdisciplinary benchmark
- Multilingual benchmark
- User study
- Public benchmark release

---

# Current Implementation State (#112)

The design above is now backed by real, runnable tooling under
`benchmark/` — see `benchmark/README` for usage:

- `benchmark/scripts/build_dataset.py` — samples journals already in
  the local database, pulls real published papers for them from
  OpenAlex (abstract, subject area, category, publication year,
  best-effort author country), and writes a versioned dataset JSON.
- `benchmark/baselines/tfidf.py` — a standalone TF-IDF / cosine-
  similarity baseline (no sklearn dependency, doesn't import any
  application code) — the "TF-IDF / keyword search" baseline this
  document calls for.
- `benchmark/scripts/evaluate.py` — runs every dataset record's
  abstract through both Scilene's real recommender
  (`services.recommender.JournalRecommender`, called exactly as the
  web app calls it) and the TF-IDF baseline, computes Recall@5/10/20
  and MRR for each, and writes a versioned report to
  `benchmark/results/`.

Not yet implemented: Subject Area / Category match rate (secondary
metrics), fairness metrics, human evaluation, and dataset versioning
beyond a single timestamped file per build (no diffing/comparison
tooling across versions yet).

**A real first result, worth stating plainly rather than hiding:** a
166-record run (60 sampled journals, seed 42) scored the deterministic
recommender at Recall@5/10/20 = 0.000 and MRR = 0.000, against the
TF-IDF baseline's 0.030 / 0.042 / 0.054 and 0.021. This reflects a
real, explainable property of the current recommender when called
with an abstract but no confirmed tags (the only fair way to benchmark
"just an abstract" today, since Research Interpreter suggestions are
still a hardcoded placeholder pool, not real analysis — see
`docs/RESEARCH_INTERPRETER.md`): its title/abstract keyword-fallback
path (`services/recommender.py`) requires at least 3 distinct keyword
hits against a journal's (often short) subjects/keywords fields, and
generic fallback words extracted from a real abstract rarely clear
that bar for the paper's own home journal. This is exactly the kind of
evidence this benchmark exists to surface — it is not a benchmark bug
(spot-checked directly: the true journal reliably appears as a
`search_candidates()` candidate, just not with enough distinct
keyword hits to survive scoring), and it is not something this pass
fixes — changing the recommender's matching threshold is a separate,
deliberate decision, not a side effect of building the measurement
tool. See `benchmark/results/20260808-133549.json` for the full report.