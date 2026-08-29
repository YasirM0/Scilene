# Ranking System

**Status (added retroactively, #149):** early Version 0.1 design doc,
not updated as the real implementation diverged. What actually shipped
is TWO separate ranking engines, not the five-stage pipeline below in
one system: `services/recommender.py` (deterministic keyword-hit
scoring -- no semantic similarity anywhere in it) and
`services/semantic_search.py` (AI Semantic Search -- embedding
similarity, now the default, falling back to the deterministic engine
automatically if it errors or finds nothing). "Stage 1: Semantic
Similarity" below describes what AI Semantic Search does, not the
deterministic engine, which never compares embeddings at all. See
`docs/QUERY_PIPELINE.md`'s own correction note for how the two relate.

## Purpose

The Ranking Engine determines the order in which journals are recommended to researchers.

Its primary objective is to identify journals that best match a manuscript while respecting the researcher's publishing preferences.

The Ranking Engine does not determine whether a journal is "good" or "bad." Instead, it estimates how well each journal fits a specific manuscript.

---

# Design Principles

## Transparent

Every recommendation must be explainable.

Users should understand why a journal received its position in the ranking.

---

## Preference-Aware

Researchers have different priorities.

Some prefer:

- Higher-ranked journals
- No APC
- Faster publication
- Specific indexing
- Open Access

The ranking should adapt to these preferences whenever possible.

---

## Evidence-Based

Ranking should rely only on available and verifiable information.

The system should never estimate missing values.

---

## Ranking Pipeline

The recommendation process consists of five stages.

```
User Input
      │
      ▼
Semantic Similarity
      │
      ▼
Eligibility Filters
      │
      ▼
Preference Scoring
      │
      ▼
Final Ranking
      │
      ▼
Explanation Generation
```

---

# Stage 1: Semantic Similarity

The user's manuscript title and abstract are compared against each journal's aims, scope, and subject description.

This stage determines topical relevance.

Semantic similarity is the primary factor in AI Semantic Search
specifically (see this document's Status note) -- the deterministic
engine uses keyword-hit scoring instead, never embeddings.

---

# Stage 2: Eligibility Filters

Journals that do not satisfy mandatory user requirements are removed.

Examples include:

- Required index (Scopus, SINTA)
- Maximum APC
- Publication language
- Open Access requirement

Only eligible journals proceed to the next stage.

---

# Stage 3: Preference Scoring

Eligible journals receive additional scoring based on optional user preferences.

Possible preferences include:

- Quartile preference
- APC preference
- Open Access preference
- Publisher preference (future)

Preference scoring should refine—not replace—semantic similarity.

---

# Stage 4: Final Ranking

Journals are sorted according to their Overall Match.

Higher-ranked journals should represent the best balance between topical fit and user preferences.

---

# Stage 5: Explanation Generation

Each recommendation must include a human-readable explanation describing the primary factors behind the recommendation.

The explanation should summarize why the journal is a suitable match and identify the most important contributing factors.

Version 0.1 emphasizes clarity over technical detail while leaving room for more detailed inspection in future versions.

Examples of explanation factors include:

- High topical similarity
- Matches requested publication language
- No APC
- Scopus indexed
- Open Access

The goal is for researchers to immediately understand why a journal appears in the results.

---

## Inspectable Recommendations

Every recommendation should provide enough information for users to understand why it was generated.

Future versions may allow users to inspect the contribution of individual ranking factors, such as semantic similarity, indexing, APC, and publication language.

Transparency should increase as the system evolves, never decrease.

---

# Transparency

Version 0.1 prioritizes explainability over algorithmic complexity.

Every score should be traceable to identifiable factors.

---

# Future Enhancements

Possible future ranking factors include:

- Historical quartiles
- Community submission experiences
- Review duration
- Acceptance probability
- Citation metrics
- Custom weighting

These features are outside the scope of Version 0.1.

---

# Out of Scope

Version 0.1 does not include:

- AI-generated acceptance predictions
- Estimated acceptance rates
- Reviewer simulation
- Citation prediction
- Journal prestige estimation beyond available metadata

---

# Version 0.1 Scope

Version 0.1 ranks journals using:

- Semantic similarity
- User-selected filters
- User preferences
- Transparent explanations

The system intentionally favors reliability and interpretability over sophisticated but opaque ranking methods.

---

**Document Version:** 0.1

**Last Updated:** July 2026

**Status:** Approved