"""
Single source of truth for application identity: name, version,
author, license, and repository. Consumed by the web layer (FastAPI
app title/version, and every Jinja template via web/templating.py's
"app" global -- the same pattern as nav_links) and by report
generation (services/report_context.py), so renaming the product or
bumping the version never means touching more than this one file.

web/config.py's Settings stays separate on purpose -- it's genuinely
environment-driven runtime config (host/port/debug), not identity.

Name note: the project's brand identity (logo, About page, README)
already establishes "Scilene" as the current name -- this file follows
that, not the older "Journal Intelligence" name still visible in a few
older code comments and docstrings (harmless, not user-facing).
"""

from types import SimpleNamespace

APP_NAME = "Scilene"
APP_VERSION = "0.2.5"
APP_AUTHOR = "Yasir Mohammed"
APP_GITHUB = "https://github.com/YasirM0/Scilene"
APP_LICENSE = "MIT"

# Sources actually imported by scripts/build_database.py's core
# indexing pipeline (not the enrichment providers in
# docs/ENRICHMENT.md, which are display-only). Kept as a plain string
# describing the pipeline's design, not a live query.
DATABASE_SOURCES = "DOAJ, Scopus, Web of Science, SINTA"

# Dotted-attribute access for Jinja templates, e.g. {{ app.name }} --
# a dict would need {{ app.name }} to actually mean {{ app['name'] }},
# which Jinja does support, but a namespace reads the same as a real
# object and matches how `settings` was used before this existed.
APP = SimpleNamespace(
    name=APP_NAME,
    version=APP_VERSION,
    author=APP_AUTHOR,
    github=APP_GITHUB,
    license=APP_LICENSE,
)


def export_prefix():
    """
    Short, filename-safe prefix for exported reports, derived from
    APP_NAME so a rename never leaves a stale filename behind. Was
    hardcoded "ji" before this existed.
    """
    return "".join(ch if ch.isalnum() else "_" for ch in APP_NAME.lower())
