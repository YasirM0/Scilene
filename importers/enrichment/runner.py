"""
Runs an OfflineEnrichmentProvider against every journal already in the
database, tagging matches into journal_enrichment via
services.repository.tag_enrichment. Never creates a new journal row --
a provider that can't match a journal by ISSN just skips it (see
docs/ENRICHMENT.md).
"""

from services.repository import tag_enrichment


class _MinimalJournal:
    """
    Just enough of the Journal shape (issn_print/issn_online) for a
    provider's fetch() to match against. Avoids building full Journal
    objects (with the journal_sources join) for every row during a
    bulk enrichment pass, which only ever needs the ISSNs.
    """

    def __init__(self, issn_print, issn_online):
        self.issn_print = issn_print
        self.issn_online = issn_online


def run_offline_provider(provider, conn):
    rows = conn.execute("SELECT id, issn_print, issn_online FROM journals").fetchall()

    matched = 0
    for journal_id, issn_print, issn_online in rows:
        data = provider.fetch(_MinimalJournal(issn_print, issn_online))
        if data is not None:
            tag_enrichment(conn, journal_id, provider.name, data)
            matched += 1

    summary = {"provider": provider.name, "matched": matched, "total_journals": len(rows)}

    print(f"{provider.name}: {matched} / {len(rows)} journals matched")

    return summary
