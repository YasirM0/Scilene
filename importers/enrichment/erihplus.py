"""
ERIH PLUS enrichment provider.

Source columns are in Norwegian (ERIH PLUS is hosted by Sikt) --
navn_en is the English title, forlag_navn the publisher, oa_doaj /
oa_romeo the DOAJ / Sherpa Romeo flags, matching the fields the
original design (docs/ENRICHMENT.md) calls out: "ERIH PLUS indexing,
English journal titles, Publisher, URL, DOAJ flag, Sherpa Romeo flag".

Same matching rule as importers/enrichment/road.py: ISSN-only, skips
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


def _flag(value):
    return _clean(value) == "1"


class ERIHPlusProvider(OfflineEnrichmentProvider):

    name = "erihplus"

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._by_issn = None

    def _load(self):
        if self._by_issn is not None:
            return

        dataframe = pd.read_csv(self.csv_path, encoding="utf-8-sig", dtype=str)
        self._by_issn = {}

        for _, row in dataframe.iterrows():
            data = {
                "title_en": _clean(row.get("navn_en")),
                "publisher": _clean(row.get("forlag_navn")),
                "url": _clean(row.get("url")),
                "in_doaj": _flag(row.get("oa_doaj")),
                "in_sherpa_romeo": _flag(row.get("oa_romeo")),
            }
            for issn in (
                normalize_issn(row.get("tidsskriftISSNP")),
                normalize_issn(row.get("tidsskriftISSNE")),
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
