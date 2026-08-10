"""
OpenAlex online enrichment provider (#107).

Primary online provider per the issue -- OpenAlex aggregates multiple
scholarly metadata sources and exposes a clean Sources API keyed by
ISSN. Queried live, on demand, after search results already exist
(services/online_enrichment.py owns caching/retry/fallback-to-Crossref;
this module is just the HTTP call and response mapping).

Never imported by services/recommender.py. A timeout, a non-200, or a
malformed response all just mean fetch() returns None -- the caller
treats that identically to "no data available", never as an error the
user needs to see.
"""

import requests

from importers.enrichment.base import OnlineEnrichmentProvider
from services.app_info import APP_VERSION, APP_GITHUB
from utils.issn import normalize_issn

REQUEST_TIMEOUT_SECONDS = 5
USER_AGENT = f"Scilene/{APP_VERSION} ({APP_GITHUB}; journal discovery platform)"


class OpenAlexProvider(OnlineEnrichmentProvider):

    name = "openalex"
    base_url = "https://api.openalex.org/sources/issn:{issn}"

    def fetch(self, journal):
        for issn in (journal.issn_print, journal.issn_online):
            issn = normalize_issn(issn)
            if not issn:
                continue

            data = self._fetch_by_issn(issn)
            if data is not None:
                return data

        return None

    def _fetch_by_issn(self, issn):
        try:
            response = requests.get(
                self.base_url.format(issn=issn),
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        try:
            payload = response.json()
        except ValueError:
            return None

        return self._map(payload)

    @staticmethod
    def _map(payload):
        apc_usd = payload.get("apc_usd")
        topics = [t.get("display_name") for t in (payload.get("topics") or [])[:3] if t.get("display_name")]

        return {
            "publisher": payload.get("host_organization_name"),
            "is_open_access": payload.get("is_oa"),
            "is_in_doaj": payload.get("is_in_doaj"),
            "apc_usd": apc_usd,
            "homepage_url": payload.get("homepage_url"),
            "topics": topics,
            "works_count": payload.get("works_count"),
            "cited_by_count": payload.get("cited_by_count"),
            "h_index": (payload.get("summary_stats") or {}).get("h_index"),
            "openalex_url": payload.get("id"),
        }
