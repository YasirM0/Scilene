# System Architecture

## Overview

Scilene follows a modular architecture designed around one principle:

> **Each module should have a single, well-defined responsibility.**

Modules communicate through clear interfaces, allowing individual components to be improved or replaced without affecting the rest of the system.

This design makes the project easier to maintain, test, and extend as new contributors join.

---

# Architecture Overview

```
                   User
                     │
                     ▼
            ┌─────────────────┐
            │       UI        │
            └─────────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Search Engine   │
            └─────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
 ┌─────────────────┐    ┌─────────────────┐
 │ Ranking Engine  │    │     Filters     │
 └─────────────────┘    └─────────────────┘
          │                     │
          └──────────┬──────────┘
                     ▼
            ┌─────────────────┐
            │ Journal Database│
            └─────────────────┘
```

---

# Core Modules

## User Interface (UI)

Responsible for:

- Collecting user input
- Displaying journal recommendations
- Presenting ranking explanations
- Exporting results

The UI should not contain business logic or ranking algorithms.

---

## Search Engine

Responsible for:

- Processing user queries
- Performing semantic similarity search
- Retrieving candidate journals

The Search Engine does not rank journals beyond finding relevant candidates.

---

## Ranking Engine

Responsible for:

- Combining semantic similarity with user-selected filters
- Producing transparent recommendation scores
- Explaining why journals are recommended

Every recommendation should be reproducible and explainable.

---

## Filters

Responsible for applying user-selected constraints such as:

- DOAJ / Scopus / Web of Science / SINTA (preferred indexing)
- Quartile
- SINTA Level
- APC
- Language
- Subject/Category (`services/subject_taxonomy.py`, DOAJ LCC categories
  and OpenAlex fields unioned)

Filters reduce the candidate list before the final ranking.

---

## Journal Database

Responsible for storing journal metadata.

Examples include:

- Journal information
- Scope
- Publisher
- Indexing
- Language
- APC
- Other publicly available metadata

The database should not contain ranking logic.

---

# Separation of Responsibilities

Each module should perform one task only.

For example:

- The UI should never calculate similarity.
- The Search Engine should never modify database records.
- The Database should never calculate rankings.
- The Ranking Engine should never directly interact with the user interface.

Keeping responsibilities separate improves maintainability and testing.

---

# Design Principles

## Transparency

Recommendations must be explainable.

Users should understand why a journal is recommended rather than receiving an unexplained score.

---

## Modularity

Modules should be replaceable without redesigning the system.

For example, changing the database or embedding model should require minimal changes to other modules.

---

## Offline First

The core recommendation system should work without requiring external APIs.

Optional AI integrations may be added in future versions but must never become mandatory.

---

## Privacy First

No user data should be stored without explicit user consent.

Users should always know what information is stored and why.

---

## Reproducibility

The same inputs and settings should produce the same recommendations.

This makes results easier to verify and trust.

---

## Evidence Before Assumptions

The project should clearly distinguish between:

- verified information
- estimated information
- unavailable information

The system should never invent missing data.

---

# Future Modules

The architecture allows additional modules to be added without changing the existing design.

Examples include:

- AI Assistant
- Submission Planner
- Community Statistics
- User Profiles
- Plugin System
- Full Manuscript Analysis

These modules are intentionally outside the scope of Version 0.1.

---

# Version 0.1 Scope

Version 0.1 consists of five primary components:

1. User Interface
2. Search Engine
3. Ranking Engine
4. Filters
5. Journal Database

The goal is to build a reliable foundation before expanding into more advanced functionality.

---

**Document Version:** 0.1

**Last Updated:** July 2026

**Status:** Approved