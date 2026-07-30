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