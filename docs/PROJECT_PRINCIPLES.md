# Project Principles

Scilene is guided by a small set of principles that influence every design decision.

When proposing a new feature, changing the architecture, or reviewing a contribution, contributors should evaluate whether the change aligns with these principles.

---

# 1. Solve One Problem Well

The primary goal of Scilene is to help researchers choose appropriate journals for their work.

Features that do not directly support this goal should be carefully evaluated before being included.

We prefer a small number of reliable features over a large number of incomplete ones.

---

# 2. Transparency Over Black Boxes

Every recommendation should be explainable.

Transparency extends beyond displaying a final result. Users should understand why a journal is recommended and be able to inspect the major factors that contributed to the recommendation.

Artificial intelligence should enrich and assist the recommendation process, not replace explainable decision-making.

Recommendations should remain understandable by humans, not only interpretable by algorithms.

The project should avoid opaque algorithms whenever practical.

---

# 3. Evidence Before Assumptions

Recommendations should be based on verifiable information.

If information is unavailable, the system should clearly communicate that rather than guessing.

Unknown values are preferable to incorrect values.

---

# 4. Simplicity Before Complexity

Simple solutions should always be preferred when they adequately solve the problem.

New features should be introduced only when they provide clear value to researchers.

Complexity should never be added solely because it is technically possible.

When multiple solutions are available, prefer the one that is easier to understand, maintain, and validate.

---

# 5. Privacy by Design

Users should always remain in control of their research.

No manuscript, abstract, or personal information should be stored without explicit user consent.

Optional features that require data collection must always be transparent, voluntary, and clearly explained.

Whenever practical, research should remain on the user's own device.

---

# 6. Fairness by Design

Researchers should receive recommendations based on the quality and meaning of their research—not on their writing style, native language, or familiarity with publishing terminology.

Whenever possible, Scilene should reduce barriers rather than expect users to adapt to the system.

---

# 7. Modular Architecture

Each component should have a single, well-defined responsibility.

Modules should be easy to replace, improve, or extend without affecting unrelated parts of the system.

The recommendation engine should remain independent from any specific AI model, inference provider, or deployment platform.

---

# 8. Ownership Over Dependency

Scilene's website exists to make discovery easy.

The desktop application is the primary long-term research experience.

Researchers should always have access to a complete, privacy-respecting version of Scilene that can continue to function independently of online services whenever practical.

The web edition lowers the barrier to entry.

The desktop edition provides long-term ownership.

---

# 9. Community First

Scilene is an open-source project.

Ideas, discussions, bug reports, and contributions are welcomed from the research community.

Respectful collaboration is considered one of the project's strengths.

---

# 10. Build for Researchers

Every feature should answer a simple question:

> Does this genuinely help a researcher make a better publishing decision?

If the answer is no, the feature probably belongs in a future version rather than the current release.

---

# Guiding Question

When uncertain about a design decision, ask:

> "Will this make Scilene more trustworthy, more understandable, more fair, or more useful to researchers?"

If not, reconsider the change.

---

**Document Version:** 0.2

**Last Updated:** July 2026

**Status:** Approved