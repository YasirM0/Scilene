"""
ROAD (Directory of Open Access Scholarly Resources) enrichment provider.

ROAD data is distributed as a TSV file (data/enrichment/road.tsv) --
this reads it directly with pandas' sep="\t", not importers/csv_importer
.py's CSVImporter, which assumes comma-separated input.

Matches rows against existing journals by ISSN only -- unlike
importers/sinta.py, an unmatched row is skipped, never turned into a
new journal row. Enrichment only attaches data to journals that
already exist and never affects search/filtering/ranking (see
docs/ENRICHMENT.md).
"""

import pandas as pd

from importers.enrichment.base import OfflineEnrichmentProvider
from utils.issn import normalize_issn


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip()
    return value or None


class ROADProvider(OfflineEnrichmentProvider):

    name = "road"

    def __init__(self, tsv_path):
        self.tsv_path = tsv_path
        self._by_issn = None

    def _load(self):
        if self._by_issn is not None:
            return

        dataframe = pd.read_csv(self.tsv_path, sep="\t", encoding="utf-8", dtype=str)
        self._by_issn = {}

        for _, row in dataframe.iterrows():
            data = {
                "title": _clean(row.get("publication_title")),
                "publisher": _clean(row.get("publisher_name")),
                "url": _clean(row.get("title_url")),
            }
            for issn in (
                normalize_issn(row.get("print_identifier")),
                normalize_issn(row.get("online_identifier")),
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
