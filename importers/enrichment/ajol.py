"""
AJOL (African Journals Online) enrichment provider.

Not mentioned in the original #99 issue text -- the data file was
collected afterward for the same purpose (see docs/ENRICHMENT.md).
Same matching rule as the other offline providers: ISSN-only, skips
unmatched rows rather than creating new journals.
"""

import pandas as pd

from importers.enrichment.base import OfflineEnrichmentProvider
from utils.issn import normalize_issn


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip()
    return value or None


class AJOLProvider(OfflineEnrichmentProvider):

    name = "ajol"

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._by_issn = None

    def _load(self):
        if self._by_issn is not None:
            return

        dataframe = pd.read_csv(self.csv_path, dtype=str)
        self._by_issn = {}

        for _, row in dataframe.iterrows():
            data = {
                "title": _clean(row.get("source_title")),
                "url": _clean(row.get("source_url")),
                "country": _clean(row.get("country")),
                "is_diamond": _clean(row.get("is_diamond")) == "1",
                "status": _clean(row.get("jjps_status")),
            }
            for issn in (
                normalize_issn(row.get("issn_print")),
                normalize_issn(row.get("eissn")),
            ):
                if issn:
                    self._by_issn.setdefault(issn, data)

    def fetch(self, journal):
        self._load()
        for issn in (journal.issn_print, journal.issn_online):
            issn = normalize_issn(issn)
            if issn and issn in self._by_issn:
                return self._by_issn[issn]
        return None
