# Data Sources

## Purpose

This document describes the public sources used to build and maintain the Journal Intelligence database.

The project prioritizes reliable, publicly available, and verifiable information.

Whenever multiple sources provide the same information, official sources should be preferred.

---

# Design Principles

## Official Sources First

Whenever possible, journal information should be obtained directly from official publishers or indexing services.

---

## Public Information Only

Version 0.1 uses publicly available information.

The project does not rely on proprietary datasets or information that requires special access.

---

## Verifiable Data

Every piece of stored information should be traceable to a reliable source.

If information cannot be verified, it should not be included.

---

# Primary Data Sources

## Journal Websites

Used for:

- Aims & Scope
- Journal Description
- APC information
- Publication Language
- Publication Frequency
- Open Access information
- Publisher details

These are considered the authoritative source for journal-specific information.

---

## Scopus

Used for:

- Scopus indexing status
- Subject classification
- Quartile information (where available)

---

## SINTA

Used for:

- SINTA ranking
- Accreditation status

Note: SINTA's own export lists a journal once per listing (observed:
once per subject-area classification) rather than once per journal, so
the raw row count is not the journal count -- `importers/sinta.py`
deduplicates on SINTA's own `journal_id` column and reports both
numbers (raw rows vs. distinct journals) in its import summary. If a
future export's row count looks like it doesn't match what ends up in
the database, check that printed summary first before assuming data
went missing.

---

## DOAJ

Used for:

- Open Access verification
- Journal metadata

---

# Future Data Sources

Future versions may incorporate additional public sources, including:

- Crossref
- OpenAlex
- Dimensions (where permitted)
- Directory services
- Community-contributed metadata

Any additional source should satisfy the project's principles of transparency and verifiability.

---

# Data Validation

When information from multiple sources differs:

1. Prefer official journal websites whenever appropriate.
2. Prefer official indexing services for indexing-related metadata.
3. Record unknown values instead of making assumptions.

The project should never invent missing information.

---

# Out of Scope

Version 0.1 does not include:

- Proprietary commercial datasets
- User-submitted journal ratings
- Estimated metrics
- AI-generated metadata

---

# Version 0.1 Scope

Version 0.1 relies on a small number of trusted public sources to ensure that recommendations remain reliable, reproducible, and transparent.

Additional data sources may be introduced only when they improve recommendation quality without compromising these principles.

---

**Document Version:** 0.1

**Last Updated:** July 2026

**Status:** Approved