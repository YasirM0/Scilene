# Project Decisions

## Purpose

This document records significant architectural and product decisions made during the development of Scilene.

Its purpose is to preserve the reasoning behind important decisions so that contributors understand not only *what* was decided, but also *why* those decisions were made.

Decision records provide historical context and help maintain consistency as the project evolves.

---

# What Should Be Recorded

Only decisions with long-term impact should be included.

Examples include:

- Technology selection
- Architectural changes
- Ranking methodology
- Privacy and data policies
- User experience philosophy
- Version scope decisions
- Major design changes

Routine implementation details should not be recorded.

---

# Decision Format

Each decision should follow the structure below.

## Decision #XXX

**Date:**

**Status:** Proposed / Accepted / Superseded

### Decision

A concise statement describing the decision.

### Context

The problem or situation that required a decision.

### Alternatives Considered

A summary of the alternatives that were evaluated.

### Reasoning

Why this option was selected.

### Consequences

Expected impact of the decision on the project.

---

# Current Decisions

## Decision #001

**Date:** July 2026

**Status:** Accepted

### Decision

Version 0.1 will prioritize reliability over feature count.

### Context

During project planning, numerous advanced ideas were proposed, including AI integration, full manuscript analysis, community features, and submission tracking.

Implementing these features in the first release would increase complexity and delay delivery.

### Alternatives Considered

- Develop many features simultaneously.
- Focus on a single core capability.

### Reasoning

The project's primary goal is to help researchers identify appropriate journals through transparent and explainable recommendations.

A focused and reliable MVP provides greater value than a feature-rich but incomplete application.

### Consequences

- Version 0.1 focuses on title and abstract recommendations.
- Advanced features are postponed to future releases.
- Every new feature must align with the project's guiding principles.

---

## Decision #002

**Date:** August 2026

**Status:** Accepted

### Decision

Scilene Web and Scilene Desktop have different, honestly-communicated
roles: Web is for immediate, installation-free discovery; Desktop is
the recommended platform for everyday research, prioritizing privacy,
local ownership, offline access, and (later) advanced local AI
capabilities. The difference is based on genuine technical
capabilities the two platforms actually have — never an artificial
restriction placed on the web edition to push users toward Desktop.

### Context

Desktop doesn't exist yet (see ARCHITECTURE_DECISIONS.md's "Future
Desktop" entry — not being built yet, web has priority) — but the
project needed to define *why* a desktop edition will eventually exist
and how it should relate to the web edition, before either building it
or writing any marketing copy that references it.

### Alternatives Considered

- Web and Desktop as functionally identical, desktop existing purely
  for offline convenience.
- Desktop as a paid/premium tier with web deliberately limited to
  create upgrade pressure.

### Reasoning

A paid-tier or artificially-limited-web approach directly contradicts
the project's own principles (`docs/PROJECT_PRINCIPLES.md` #8,
"Ownership Over Dependency": "The web edition lowers the barrier to
entry. The desktop edition provides long-term ownership.") and its
"Evidence Before Assumptions" commitment to honest, non-manipulative
communication. The two editions should differ because desktop
genuinely *can* do things a browser tab can't (persistent local
storage, local model inference, no dependency on Scilene's own servers
staying up), not because a feature was deliberately withheld from web
to manufacture a reason to switch.

### Consequences

- Any future desktop-only feature must be justified by a real
  technical capability (offline access, local AI, local storage), not
  added to web and then hidden.
- Website copy that mentions a desktop download ("Download Scilene
  Desktop for local AI, offline research...") must not ship before
  a desktop edition actually exists — advertising a download that
  doesn't exist would itself violate the "never imply the web version
  is intentionally limited" principle this decision is built on.
  `web/templates/pages/home.html` does not reference Desktop yet.
- If the hosted web edition is ever discontinued or changes
  significantly, users must still retain a working, complete research
  tool via Desktop — this is a long-term commitment, not just a
  feature-parity goal.

---

# Future Decisions

Additional decision records will be added as the project evolves.

Only accepted or historically significant decisions should be preserved.

---

**Document Version:** 0.2

**Last Updated:** August 2026

**Status:** Draft