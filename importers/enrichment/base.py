"""
Base classes for metadata enrichment providers.

See docs/ENRICHMENT.md for why this is a sibling to importers/base.py
rather than a subclass of it, and for the storage model
(journal_enrichment) this is designed against.
"""


class EnrichmentProvider:
    """
    Parent class for all metadata enrichment providers.

    Unlike BaseImporter (which creates/updates rows in `journals`), a
    provider only ever attaches data to a journal that already exists
    — matched by ISSN, the same authoritative method docs/DATABASE.md
    uses for deduplication. A provider that can't match a journal by
    ISSN skips it; enrichment never creates a new journal or guesses
    a match.
    """

    name = ""  # matches journal_enrichment.provider once that table exists

    def fetch(self, journal):
        """
        Retrieve this provider's data for one journal.

        Returns a plain dict (display-only fields) or None if this
        provider has nothing for the journal. Online providers call
        an API here; offline providers look up a pre-loaded local
        dataset — see OfflineEnrichmentProvider / OnlineEnrichmentProvider.
        """
        raise NotImplementedError

    def is_online(self):
        raise NotImplementedError


class OfflineEnrichmentProvider(EnrichmentProvider):
    """
    A provider backed by a local, pre-generated dataset (a committed
    CSV/TSV, or one regenerated from an API during an annual update —
    never queried live by the running app). Runs during
    scripts/build_database.py, same as importers/.
    """

    def is_online(self):
        return False


class OnlineEnrichmentProvider(EnrichmentProvider):
    """
    A provider backed by a live API call, made on demand after search
    results already exist. Subject to docs/ENRICHMENT.md's online/
    offline consent rules: automatic on the web app, gated behind
    explicit user consent on the (not yet built) desktop app.
    """

    def is_online(self):
        return True
