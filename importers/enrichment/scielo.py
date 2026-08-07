"""
SciELO enrichment provider.

data/enrichment/scielo_journals.csv has a single ISSN column
(scielo_issn, already hyphenated) rather than separate print/online
columns. `mission` is a Python dict literal string keyed by language
(e.g. "{'es': ..., 'pt': ..., 'en': ...}"), parsed with ast.literal_eval
rather than json -- it uses single quotes, not valid JSON.

Same matching rule as road.py/erihplus.py: ISSN-only, skips unmatched
rows rather than creating new journals.
"""

import ast

import pandas as pd

from importers.enrichment.base import OfflineEnrichmentProvider
from utils.issn import normalize_issn


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip()
    return value or None


def _english_mission(raw):
    raw = _clean(raw)
    if raw is None:
        return None
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(parsed, dict):
        return None
    return _clean(parsed.get("en"))


class SciELOProvider(OfflineEnrichmentProvider):

    name = "scielo"

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._by_issn = None

    def _load(self):
        if self._by_issn is not None:
            return

        dataframe = pd.read_csv(self.csv_path, dtype=str)
        self._by_issn = {}

        for _, row in dataframe.iterrows():
            issn = normalize_issn(row.get("scielo_issn"))
            if not issn:
                continue
            data = {
                "publisher": _clean(row.get("publisher_name")),
                "status": _clean(row.get("current_status")),
                "subject_areas": _clean(row.get("subject_areas")),
                "mission_en": _english_mission(row.get("mission")),
            }
            self._by_issn.setdefault(issn, data)

    def fetch(self, journal):
        self._load()
        for issn in (journal.issn_print, journal.issn_online):
            issn = normalize_issn(issn)
            if issn and issn in self._by_issn:
                return self._by_issn[issn]
        return None
