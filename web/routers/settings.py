"""
Desktop settings panel (#155) -- language, dataset auto-update, and
theme, all backed by services/prefs.py: persistent across launches,
unlike the session-scoped language switch at web/routers/locale.py or
the nav bar's own localStorage-only theme toggle (neither of those
changes here).

Registered unconditionally in web/main.py, like every other router --
importing THIS module must stay safe on a machine that never installed
requirements-desktop.txt, so services.prefs (needs platformdirs) is
only ever imported lazily, inside each route below, never at module
level. SCILENE_RUNTIME is read fresh per-request throughout (not
web/templating.py's is_desktop global, which is fixed for the whole
process and would never reflect per-request runtime differences) --
the one place that actually matters is the Arabic-on-web validation in
set_language() below.
"""

import logging
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from web.i18n import SUPPORTED_LOCALES
from web.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings")


def _is_desktop_runtime():
    return os.environ.get("SCILENE_RUNTIME") == "desktop"


@router.get("")
def settings_page(request: Request):
    from services import dataset_updater
    from services.prefs import load_prefs

    context = {
        "prefs": load_prefs(),
        "current_version": dataset_updater.get_local_version(),
        "update_pending": dataset_updater.UPDATE_PENDING,
        "pending_version": dataset_updater.PENDING_VERSION,
    }
    return templates.TemplateResponse(request=request, name="pages/settings.html", context=context)


@router.post("/language")
def set_language(language: str = Form(...)):
    if language == "ar" and not _is_desktop_runtime():
        # Web/Heroku never has Argos installed (see
        # services/query_translator.py) -- this mirrors that same
        # restriction here, at the point a preference is actually
        # saved, not just at search time.
        return JSONResponse(
            {"error": "Arabic search is only available in the Scilene desktop app."},
            status_code=400,
        )

    if language not in SUPPORTED_LOCALES:
        return JSONResponse({"error": f"Unsupported language: {language!r}"}, status_code=400)

    from services.prefs import set_pref

    set_pref("language", language)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/theme")
def set_theme(theme: str = Form(...)):
    if theme not in ("light", "dark"):
        return JSONResponse({"error": f"Unsupported theme: {theme!r}"}, status_code=400)

    from services.prefs import set_pref

    set_pref("theme", theme)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/auto-update")
def set_auto_update(enabled: str = Form(...)):
    from services.prefs import set_pref

    set_pref("dataset_auto_update", enabled.strip().lower() == "true")
    return RedirectResponse(url="/settings", status_code=303)


@router.get("/update-status")
def update_status():
    from services import dataset_updater
    from services.prefs import get_pref

    return {
        "update_available": dataset_updater.UPDATE_PENDING,
        "pending_version": dataset_updater.PENDING_VERSION,
        "current_version": dataset_updater.get_local_version(),
        "auto_update": get_pref("dataset_auto_update", True),
    }


@router.post("/apply-update")
def apply_update_now():
    """
    Manual trigger for the DATASET card's [Apply update] button --
    calls the same apply_update_with_retry() the startup thread uses
    (web/main.py), so a search in progress defers this exactly the
    same way. Runs synchronously in this sync `def` route (Starlette
    runs these in a threadpool, not the event loop, so this doesn't
    block other requests) -- a worst case of every retry finding
    SEARCH_LOCK held means this specific request can take up to
    APPLY_MAX_ATTEMPTS * APPLY_RETRY_SECONDS (~5 minutes) to respond,
    same tradeoff the startup thread already accepts.

    JSON body exactly as #155 specifies, PLUS an HX-Redirect header --
    settings.html's button is an htmx form (hx-post), not a plain one:
    a plain form POST here would navigate the browser to the raw JSON
    body instead of back to the settings page. HX-Redirect is the same
    mechanism web/routers/research_idea.py's continue_to_search()
    already uses for an htmx POST that needs to send the browser
    somewhere afterward -- htmx reads the header and navigates
    regardless of the body's content-type, so this doesn't change the
    JSON contract at all for a non-htmx (API) caller.
    """
    from fastapi.responses import JSONResponse

    from services import dataset_updater

    pending_version = dataset_updater.PENDING_VERSION
    applied = dataset_updater.apply_update_with_retry()
    if applied:
        dataset_updater.UPDATE_PENDING = False
        dataset_updater.PENDING_VERSION = None

    response = JSONResponse({"applied": applied, "version": pending_version})
    response.headers["HX-Redirect"] = "/settings"
    return response
