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

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Available in every template without each route needing to pass it
# explicitly — e.g. base.html's <title> and footer use settings.app_name
# and settings.app_version directly.
templates.env.globals["settings"] = get_settings()
