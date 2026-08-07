"""
Metadata enrichment providers.

Distinct from importers/ (which builds the journals + journal_sources
tables that search, filtering, and ranking read from): a provider here
only ever attaches display-only data to a journal that already
exists, and is never read by services/recommender.py. See
docs/ENRICHMENT.md for the full design.
"""
