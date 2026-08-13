"""
FastAPI application entrypoint.

Run with:  uvicorn web.main:app --reload   (from the project root)

This file wires up the app (settings, static files, routers) and
contains no business logic itself — that all lives in services/,
models/, importers/, utils/, which this app imports exactly as the
Streamlit app does. The intent (see docs/ARCHITECTURE.md and
docs/WEB_MIGRATION.md) is that a future desktop (Tauri) shell or a
future public API could import that same core without touching this
file at all.
"""

import sys
from pathlib import Path

# Make the project root importable (services/, models/, etc.) regardless
# of the working directory this is launched from. Same reasoning as the
# Streamlit app's app/main.py: relying on the launcher's cwd already
# being on sys.path caused a real deployment failure there once.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from services.app_info import APP_NAME, APP_VERSION
from web.config import get_settings
from web.dependencies import SESSION_COOKIE_NAME
from web.i18n import DEFAULT_LOCALE
from web.routers import (
    home, pages, search, interpreter, enrichment,
    research_idea, compare, locale as locale_router,
)
from web.session_store import get_session

settings = get_settings()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    debug=settings.debug,
)


@app.middleware("http")
async def resolve_locale(request: Request, call_next):
    """
    Makes request.state.locale available to every template (Starlette
    always injects `request` into Jinja2Templates' context, so this is
    the one place a locale resolves without threading it through every
    route's own context dict -- see web/i18n.py). Reads an EXISTING
    session's preference if the cookie is present; never creates a new
    session just to check a locale a brand-new visitor hasn't set yet
    (that would give every anonymous pageview a side effect).
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    request.state.locale = get_session(session_id).get("locale", DEFAULT_LOCALE) if session_id else DEFAULT_LOCALE
    return await call_next(request)


@app.middleware("http")
async def cache_versioned_static(request: Request, call_next):
    """
    Every /static/* URL is now requested with a ?v=<mtime> query string
    (base.html, web/static_versioning.py) that only ever changes when
    the underlying file actually does -- safe, then, to tell every
    browser to cache it as aggressively as possible ("immutable": never
    revalidate for the lifetime of this exact URL) rather than relying
    on each browser's own heuristics for an unmarked response, which is
    what let a stale copy of multiselect.js mislead a real bug report.
    Faster repeat visits for everyone as a side effect, but the reason
    this exists is correctness, not performance.
    """
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

app.include_router(home.router)
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(interpreter.router)
app.include_router(enrichment.router)
app.include_router(research_idea.router)
app.include_router(compare.router)
app.include_router(locale_router.router)
