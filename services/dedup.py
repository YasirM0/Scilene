"""
Journal deduplication / merge helpers.

Used by the import pipeline (scripts/build_database.py) to match
incoming rows from Scopus/WoS/SINTA against journals already in the
database, so each real-world journal ends up as ONE row, tagged with
every source it's confirmed in, instead of one row per source.

Match order: ISSN (print or online) first, then a normalized-title
match as a fallback — but title matching alone is NOT considered
reliable enough on its own. A real build surfaced 34 journals wrongly
merged this way (e.g. MDPI's "Vision" from Switzerland got merged with
an unrelated Indonesian journal also titled "Vision", and picked up an
incorrect SINTA tag as a result). So a title match is only accepted if
BOTH of these hold:
  1. The normalized title has at least 3 words (rules out generic
     one-word titles like "Vision", "Logos", "Forum" — these carry a
     real collision risk and aren't distinctive enough to trust alone).
  2. Neither side's country is known to conflict (if both the incoming
     row and the existing journal have a country on record, they must
     match; if either is unknown, this check doesn't block the match).

This is still not fuzzy matching — two records for the same journal
with meaningfully different titles (e.g. one includes a subtitle the
other doesn't) will not be merged and will end up as separate rows.
That's a real, deliberate limitation: safer to leave two rows for the
same journal unmerged than to risk tagging a journal with a source it
was never actually confirmed in.
"""

import re

MIN_TITLE_WORDS_FOR_MATCH = 3


def normalize_title(title):
    if not title:
        return None
    normalized = str(title).lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _normalize_country(country):
    if not country:
        return None
    return str(country).strip().lower() or None


class JournalIndex:
    """
    In-memory index of existing journals (by ISSN and normalized title),
    used to match incoming rows during import. Reflects whatever has
    already been committed to the `journals` table when it's built —
    rebuild it (or update it manually, see `add`) after writes.
    """

    def __init__(self, conn):
        self.by_issn = {}
        self.by_title = {}
        self.country_by_id = {}

        rows = conn.execute(
            "SELECT id, title, issn_print, issn_online, country FROM journals"
        ).fetchall()

        for journal_id, title, issn_print, issn_online, country in rows:
            if issn_print:
                self.by_issn.setdefault(issn_print, journal_id)
            if issn_online:
                self.by_issn.setdefault(issn_online, journal_id)
            normalized = normalize_title(title)
            if normalized:
                self.by_title.setdefault(normalized, journal_id)
            self.country_by_id[journal_id] = _normalize_country(country)

    def find(self, issns, title, country=None):
        """Returns (journal_id, match_type) or (None, None)."""
        for issn in issns:
            if issn in self.by_issn:
                return self.by_issn[issn], "issn"

        normalized = normalize_title(title)

        if not normalized:
            return None, None

        if len(normalized.split()) < MIN_TITLE_WORDS_FOR_MATCH:
            return None, None

        candidate_id = self.by_title.get(normalized)
        if candidate_id is None:
            return None, None

        existing_country = self.country_by_id.get(candidate_id)
        incoming_country = _normalize_country(country)

        if existing_country and incoming_country and existing_country != incoming_country:
            # Same title, different country on record for both sides —
            # more likely a coincidental title collision than the same
            # journal. Don't merge.
            return None, None

        return candidate_id, "title"

    def add(self, journal_id, issns, title, country=None):
        """Register a newly created journal so later rows in the same
        import (or a later source) can match against it without a
        fresh DB round-trip."""
        for issn in issns:
            self.by_issn.setdefault(issn, journal_id)
        normalized = normalize_title(title)
        if normalized:
            self.by_title.setdefault(normalized, journal_id)
        self.country_by_id[journal_id] = _normalize_country(country)