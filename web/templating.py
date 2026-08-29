"""
Single, shared Jinja2Templates instance for the whole web app.

Every router imports `templates` from here rather than constructing
its own Jinja2Templates(...) — that would mean re-registering globals
(like `app`) in multiple places and risking them drifting apart. One
instance, one source of truth, imported everywhere.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from services.app_info import APP
from web.search_presentation import CONFIDENCE_COLORS, CONFIDENCE_STARS, CONFIDENCE_STAR_COLORS
from web.static_versioning import static_version
from utils.indexing import format_source_chip, format_index_summary, format_enrichment_badges
from utils.subjects import format_subjects
from utils.aliases import format_alias_line
from utils.publication_types import format_publication_type_badge
from web.i18n import t, SUPPORTED_LOCALES

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Available in every template without each route needing to pass it
# explicitly — e.g. base.html's <title> and footer use app.name and
# app.version directly. Single source of truth: services/app_info.py.
templates.env.globals["app"] = APP

# Reused exactly as-is from the existing utils/ layer (the same
# functions the Streamlit page calls), not reimplemented here — so the
# web app's display formatting can never drift from the Streamlit
# app's while both exist side by side.
templates.env.globals["format_source_chip"] = format_source_chip
templates.env.globals["format_index_summary"] = format_index_summary
templates.env.globals["format_enrichment_badges"] = format_enrichment_badges
templates.env.globals["format_subjects"] = format_subjects
templates.env.globals["format_alias_line"] = format_alias_line
templates.env.globals["format_publication_type_badge"] = format_publication_type_badge
templates.env.globals["t"] = t
templates.env.globals["static_version"] = static_version
templates.env.globals["supported_locales"] = SUPPORTED_LOCALES
templates.env.globals["confidence_colors"] = CONFIDENCE_COLORS
templates.env.globals["confidence_stars"] = CONFIDENCE_STARS
templates.env.globals["confidence_star_colors"] = CONFIDENCE_STAR_COLORS

# Defined once, here, so every page's nav bar (via partials/nav.html)
# stays in sync automatically — a new page just needs an entry added
# to this list, not an edit to every template that renders navigation.
templates.env.globals["nav_links"] = [
    {"key": "nav.home", "href": "/"},
    {"key": "nav.search", "href": "/search"},
    {"key": "nav.statistics", "href": "/statistics"},
    {"key": "nav.about", "href": "/about"},
]
