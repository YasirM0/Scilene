"""
Single, shared Jinja2Templates instance for the whole web app.

Every router imports `templates` from here rather than constructing
its own Jinja2Templates(...) — that would mean re-registering globals
(like `settings`) in multiple places and risking them drifting apart.
One instance, one source of truth, imported everywhere.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from web.config import get_settings
from web.search_presentation import CONFIDENCE_COLORS, CONFIDENCE_STARS
from utils.indexing import format_source_chip, format_index_summary, format_enrichment_badges
from utils.subjects import format_subjects

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Available in every template without each route needing to pass it
# explicitly — e.g. base.html's <title> and footer use settings.app_name
# and settings.app_version directly.
templates.env.globals["settings"] = get_settings()

# Reused exactly as-is from the existing utils/ layer (the same
# functions the Streamlit page calls), not reimplemented here — so the
# web app's display formatting can never drift from the Streamlit
# app's while both exist side by side.
templates.env.globals["format_source_chip"] = format_source_chip
templates.env.globals["format_index_summary"] = format_index_summary
templates.env.globals["format_enrichment_badges"] = format_enrichment_badges
templates.env.globals["format_subjects"] = format_subjects
templates.env.globals["confidence_colors"] = CONFIDENCE_COLORS
templates.env.globals["confidence_stars"] = CONFIDENCE_STARS

# Defined once, here, so every page's nav bar (via partials/nav.html)
# stays in sync automatically — a new page just needs an entry added
# to this list, not an edit to every template that renders navigation.
templates.env.globals["nav_links"] = [
    {"label": "Home", "href": "/"},
    {"label": "Submission Search", "href": "/search"},
    {"label": "Academy", "href": "/academy"},
    {"label": "About", "href": "/about"},
    {"label": "Documentation", "href": "/documentation"},
]
