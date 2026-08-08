"""
Online metadata enrichment orchestration (#107).

The one entry point the web layer calls -- queries every provider
(not just until the first success) and merges their fields (#108's
"Merge enrichment results" -- OpenAlex's value wins per field when
both have one, since it's the richer API; Crossref only fills fields
OpenAlex left empty), plus a short retry on a transient miss and a
process-wide in-memory TTL cache (mirrors web/search_cache.py's
pattern/reasoning: identical input, identical result, no reason to
scope per-session). Metadata like publisher/APC doesn't change minute
to minute, so a day-long TTL is generous, not risky.

Deliberately NOT imported by services/recommender.py or anything in
the deterministic search path (see docs/ENRICHMENT.md) -- this only
ever runs on an explicit, per-journal user action
(web/routers/enrichment.py), after search results already exist, and
never blocks or slows down a search itself. If both providers fail --
a missing ISSN, an unreachable API, offline, a journal neither source
covers -- enrich() returns None and the caller treats that identically
in every case: omit the enrichment, never show an error.
"""

import time

from importers.enrichment.openalex import OpenAlexProvider
from importers.enrichment.crossref import CrossrefProvider

_CACHE_TTL_SECONDS = 60 * 60 * 24
_CACHE_MAX_ENTRIES = 500
_cache = {}  # (issn_print, issn_online) -> (cached_at, result_or_None)

_PROVIDERS = [OpenAlexProvider(), CrossrefProvider()]

_FETCH_ATTEMPTS = 2  # one retry -- providers already swallow network errors into None internally


class _MinimalJournal:
    """Just enough of the Journal shape for a provider's fetch()."""

    def __init__(self, issn_print, issn_online):
        self.issn_print = issn_print
        self.issn_online = issn_online


def enrich(issn_print, issn_online):
    """
    Returns {"providers": ["openalex", "crossref", ...], "data": {...}}
    -- `data` is the union of every responding provider's fields
    (earlier providers in _PROVIDERS win a field both have), `providers`
    lists only the ones that actually had something. None if nobody did.
    """

    cache_key = (issn_print or "", issn_online or "")
    if not cache_key[0] and not cache_key[1]:
        return None

    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    journal = _MinimalJournal(issn_print, issn_online)

    contributors = []
    merged_data = {}
    for provider in _PROVIDERS:
        data = _fetch_with_retry(provider, journal)
        if not data:
            continue
        contributors.append(provider.name)
        for key, value in data.items():
            if key not in merged_data and value not in (None, "", []):
                merged_data[key] = value

    result = {"providers": contributors, "data": merged_data} if contributors else None

    if len(_cache) >= _CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))  # drop the oldest entry (dicts preserve insertion order)

    _cache[cache_key] = (time.time(), result)

    return result


def _fetch_with_retry(provider, journal):
    for _ in range(_FETCH_ATTEMPTS):
        try:
            data = provider.fetch(journal)
        except Exception:
            # Last line of defense -- a provider bug must never break
            # the results page. Providers already handle their own
            # network/parsing errors internally and return None; this
            # only catches something genuinely unexpected.
            data = None
        if data:
            return data
    return None
