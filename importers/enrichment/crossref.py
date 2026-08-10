"""
Crossref online enrichment provider (#107).

Fallback provider, used when OpenAlex has nothing for a journal's ISSN
(see services/online_enrichment.py for the fallback order). Crossref's
Journals API is thinner than OpenAlex's Sources API -- no APC, no
Open Access status, no topics -- but it's a different, independent
source, so it can succeed where OpenAlex has a gap.
"""

import requests

from importers.enrichment.base import OnlineEnrichmentProvider
from services.app_info import APP_VERSION, APP_GITHUB
from utils.issn import normalize_issn

REQUEST_TIMEOUT_SECONDS = 5
USER_AGENT = f"Scilene/{APP_VERSION} ({APP_GITHUB}; mailto:none)"


class CrossrefProvider(OnlineEnrichmentProvider):

    name = "crossref"
    base_url = "https://api.crossref.org/journals/{issn}"

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
            payload = response.json().get("message") or {}
        except ValueError:
            return None

        if not payload:
            return None

        return self._map(payload)

    @staticmethod
    def _map(payload):
        counts = payload.get("counts") or {}
        total_dois = counts.get("total-dois")

        return {
            "publisher": payload.get("publisher"),
            "subjects": (payload.get("subjects") or [])[:3],
            "total_works": total_dois,
        }
