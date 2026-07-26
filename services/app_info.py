"""
Single source of truth for values that show up in exported reports and
could plausibly appear elsewhere later (an About page, logs, etc.).
Bump APP_VERSION here when the milestone number changes — nowhere else
hardcodes it.
"""

APP_VERSION = "0.1.9"

# Sources actually imported by scripts/build_database.py. Kept as a
# plain string (not derived from a live query) because it describes the
# pipeline's design, not a specific database snapshot — update this if a
# new source is added to the build pipeline.
DATABASE_SOURCES = "DOAJ, Scopus, Web of Science, SINTA"
