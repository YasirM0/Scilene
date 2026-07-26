# User Interface Design

## Purpose

The user interface provides a simple and intuitive way for researchers to discover journals that fit their manuscripts.

Version 0.1 focuses on usability, transparency, and speed.

The interface should help users reach a recommendation with minimal effort while allowing advanced users to customize their search.

---

# Design Principles

## Simplicity First

The interface should minimize unnecessary complexity.

A first-time user should be able to obtain recommendations without reading documentation.

---

## Transparency

Recommendations should always be accompanied by an explanation.

Researchers should immediately understand why a journal appears in the results rather than seeing only a numerical assessment.

---

## Progressive Disclosure

Basic functionality should be immediately accessible.

Advanced options should remain available without overwhelming new users.

---

# User Workflow

```
Open Application
        │
        ▼
Choose Search Mode
        │
        ▼
Enter Manuscript Information
        │
        ▼
(Optional) Configure Preferences
        │
        ▼
Search
        │
        ▼
View Recommendations
        │
        ▼
Inspect Journal Details
        │
        ▼
Export Results
```

---

# Search Modes

## Simple Mode

Designed for researchers who want recommendations quickly.

### Required Fields

- Manuscript Title
- Abstract

### Optional Fields

- Keywords

The system applies default settings and returns ranked recommendations.

---

## Advanced Mode

Allows researchers to customize recommendations.

Additional options include:

- Index selection (Scopus, SINTA)
- Quartile preference
- Maximum APC
- Publication language
- Open Access requirement

Future versions may introduce additional filters.

---

# Recommendation Results

Each recommendation should display:

- Journal Name
- Overall Match
- Top Reasons
- Publisher
- Indexes
- Quartile (if available)
- SINTA Rank (if available)
- APC information
- Publication language
- Open Access status

Each recommendation should also provide a link to the journal's official website.

Example:

```
Journal of Regional Development

Overall Match
92%

Top Reasons

✓ Strong topical similarity
✓ Scopus indexed
✓ No APC
✓ English publication
```

The recommendation should prioritize explanation before numerical assessment.

Researchers should immediately understand why a journal appears in the results.

---

# Journal Details

Selecting a journal should display additional information, including:

- Aims & Scope
- Journal Description
- Subject Areas
- Keywords
- Publication Frequency
- ISSN / eISSN

Future versions may provide a more detailed explanation of how individual ranking factors contributed to the recommendation.

---

# Export

Users should be able to export recommendation results.

Supported formats for Version 0.1:

- CSV
- JSON
- Markdown

Future versions may support additional formats.

---

# Error Handling

The interface should provide clear messages when:

- Required fields are missing.
- No matching journals are found.
- Filters are too restrictive.
- Data is unavailable.

Error messages should explain the problem and, whenever possible, suggest a solution.

---

# Accessibility

The interface should prioritize readability.

Where practical, it should:

- Use clear labels
- Avoid unnecessary jargon
- Support keyboard navigation
- Display important information consistently

Accessibility improvements will continue in future versions.

---

# Out of Scope

Version 0.1 does not include:

- User accounts
- Saved searches (persisted across sessions/devices)
- Cloud synchronization
- AI chat assistant
- Collaboration features

Session-only search history (cleared when the browser session ends,
never written to the database) was added in v0.1.8 — see
docs/RECOMMENDATIONS.md.

---

# Version 0.1 Scope

Version 0.1 provides a lightweight interface that enables researchers to:

- Enter manuscript information
- Configure basic preferences
- Receive transparent journal recommendations
- Understand why journals are recommended
- Review journal information
- Revisit recent searches from the same browser session
- Export results as PDF, DOCX, XLSX, Markdown, or CSV — see
  docs/EXPORT.md

The interface prioritizes clarity, transparency, and usability over feature richness.

---

**Document Version:** 0.1

**Last Updated:** July 2026

**Status:** Approved