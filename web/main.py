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

import argparse
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from services.app_info import APP_NAME, APP_VERSION
from web.config import get_settings
from web.rate_limit import limiter
from web.dependencies import SESSION_COOKIE_NAME
from web.i18n import DEFAULT_LOCALE
from web.routers import (
    home, pages, search, interpreter, enrichment,
    research_idea, compare, locale as locale_router, settings as settings_router,
)
from web.session_store import get_session

logger = logging.getLogger(__name__)

settings = get_settings()

# #155 -- what resolve_locale() below falls back to for a brand-new
# session (no cookie yet). A plain module-level variable, not the
# DEFAULT_LOCALE import above directly: `from web.i18n import
# DEFAULT_LOCALE` binds this module's own name to whatever
# DEFAULT_LOCALE's value was AT IMPORT TIME -- later reassigning
# web.i18n.DEFAULT_LOCALE itself wouldn't change what this file's own
# `DEFAULT_LOCALE` name refers to. lifespan() reassigns THIS variable
# instead, once, at desktop startup, from the language pref.
_startup_default_locale = DEFAULT_LOCALE


def _run_dataset_update_check():
    """
    Runs in a daemon thread started by lifespan() below, never on the
    request-handling path -- #153. Two separate check_remote_version()
    calls (one inside is_update_available(), one direct) rather than
    one: is_update_available() only returns a bool per its own spec,
    and this needs the actual db_url/sha256/size_bytes to download,
    so there's no way to get both without either two GETs or changing
    that function's return type. version.json is tiny (a few hundred
    bytes) against a 3s timeout each, so the redundant fetch costs
    little.
    """
    from services import dataset_updater

    logger.info("Checking for dataset updates...")

    if not dataset_updater.is_update_available():
        logger.info("Dataset is up to date (local version %s)", dataset_updater.get_local_version())
        return

    remote = dataset_updater.check_remote_version()
    if not remote:
        # Reachable during is_update_available()'s own check a moment
        # ago, unreachable now (network dropped, host started
        # rejecting) -- same "give up for this launch" response as
        # never having been reachable in the first place.
        logger.info("Dataset update was available a moment ago but version.json is unreachable now")
        return

    logger.info(
        "Dataset update available: local=%s remote=%s",
        dataset_updater.get_local_version(), remote["version"],
    )

    downloaded = dataset_updater.download_update(
        remote["db_url"], remote["sha256"], remote.get("size_bytes")
    )
    if not downloaded:
        logger.warning("Dataset download failed or failed checksum verification; keeping current version")
        return

    dataset_updater.stage_pending_version(remote["version"])

    # #155 -- whether this actually applies now or just gets flagged
    # UPDATE_PENDING for the user to confirm via /settings depends on
    # the dataset_auto_update pref; maybe_apply_update() owns that
    # decision (and the logging for each branch) so it isn't
    # duplicated between here and POST /settings/apply-update's manual
    # trigger path.
    if dataset_updater.maybe_apply_update(remote["version"]):
        logger.info("Dataset updated to version %s", remote["version"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Desktop only (#153/#155) -- on Heroku/web, the DB is refreshed by
    # scripts/publish_dataset_update.py + a manual redeploy, exactly
    # like today, and there's no persistent per-install language pref
    # to read at all; SCILENE_RUNTIME unset (the safe default -- see
    # services/query_translator.py's identical reasoning for Arabic)
    # means "assume web" here too.
    if os.environ.get("SCILENE_RUNTIME") == "desktop":
        global _startup_default_locale
        from services.prefs import get_pref

        _startup_default_locale = get_pref("language", DEFAULT_LOCALE)

        threading.Thread(
            target=_run_dataset_update_check, daemon=True, name="dataset-update-check",
        ).start()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    debug=settings.debug,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
async def health():
    """
    Liveness probe for the Tauri shell (#152): the sidecar spawns
    uvicorn on a random port and polls this before showing the
    webview, since the process existing doesn't mean it's accepting
    requests yet.
    """
    return {"status": "ok", "version": APP_VERSION}


# #151 -- native OS chrome (window title, menu labels) has no
# per-request locale of its own the way a page render does
# (request.state.locale, set below): there's exactly one native window
# for the whole desktop process, so this reflects the PERSISTED
# language pref (services.prefs, desktop-only), not any particular
# browser session's cookie. Distinct from the window-title strings a
# page itself might show -- this is purely for src-tauri/src/lib.rs to
# call once after the webview is ready.
WINDOW_TITLES = {
    "en": "Scilene — Journal Intelligence",
    "ar": "سيلين — ذكاء المجلات",
    "id": "Scilene — Kecerdasan Jurnal",
}
RTL_LANGUAGES = {"ar"}


@app.get("/api/window-title")
async def window_title():
    language = "en"
    if os.environ.get("SCILENE_RUNTIME") == "desktop":
        from services.prefs import get_pref

        language = get_pref("language", "en")

    if language not in WINDOW_TITLES:
        language = "en"

    return {
        "title": WINDOW_TITLES[language],
        "rtl": language in RTL_LANGUAGES,
        "language": language,
    }


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
    request.state.locale = (
        get_session(session_id).get("locale", _startup_default_locale) if session_id else _startup_default_locale
    )
    return await call_next(request)


@app.middleware("http")
async def resolve_theme(request: Request, call_next):
    """
    Makes request.state.theme available to base.html (#155) -- None on
    web (services.prefs needs platformdirs, not installed there; the
    existing localStorage + inline-script mechanism in base.html/
    nav.html is untouched and keeps working exactly as before). Read
    fresh per-request, not cached at startup like _startup_default_locale
    above: unlike the language default (only relevant once, for a
    brand-new session), theme can change mid-run via POST
    /settings/theme and every subsequent page load must reflect that
    immediately, prefs.json read cost is negligible either way.
    """
    request.state.theme = None
    if os.environ.get("SCILENE_RUNTIME") == "desktop":
        from services.prefs import get_pref

        request.state.theme = get_pref("theme", "light")
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    #146 — defensive headers. All resources (scripts, styles, images)
    are served from the same origin, so the CSP, COOP, COEP, and CORP
    headers below are safe without any allowlist exceptions.

    CSP carries 'unsafe-inline' for script-src and style-src because:
      - base.html has an inline <script> that sets the dark-mode class
        before first paint (cannot defer without a flash-of-wrong-theme)
      - nav.html has an inline <script> for the theme-toggle listener
      - bar_list.html sets width via style="…" (dynamic %, can't be a class)
    The other CSP directives (object-src, base-uri, form-action,
    frame-ancestors) still provide real protection regardless.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    return response


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


if getattr(sys, "frozen", False):
    # PyInstaller's onefile bootloader places the __main__ entry script
    # (this file) at the bundle root rather than preserving its
    # original web/ path, unlike normally-imported modules (e.g.
    # web/templating.py's identical Path(__file__)... pattern), which
    # DO keep their real path under sys._MEIPASS -- so only this one
    # __file__-relative lookup needs a frozen-mode branch. Verified by
    # running the frozen binary: "Directory '/tmp/_MEIxxxx/static' does
    # not exist" (looked one level too shallow) before this existed.
    STATIC_DIR = Path(sys._MEIPASS) / "web" / "static"
else:
    STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(home.router)
app.include_router(pages.router)
app.include_router(search.router)
app.include_router(interpreter.router)
app.include_router(enrichment.router)
app.include_router(research_idea.router)
app.include_router(compare.router)
app.include_router(locale_router.router)
app.include_router(settings_router.router)


if __name__ == "__main__":
    # Only reached when the Tauri sidecar (#152) launches the frozen
    # binary directly (`scilene-server --port N`) -- the web/Heroku
    # deploy always runs `uvicorn web.main:app` instead (see Procfile),
    # never this file as a script. --port is required so the sidecar
    # can bind whatever free port it picked before spawning.
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()
    # `app` directly, NOT the "web.main:app" string -- the string form
    # makes uvicorn re-import "web.main" by dotted path, which only
    # exists as __main__ inside the frozen PyInstaller bundle (nothing
    # else imports web.main as a submodule, unlike web.config/web.routers/
    # etc), so it fails with "Could not import module 'web.main'" the
    # instant the sidecar actually starts. The string form only matters
    # for uvicorn's reload=True/multi-worker modes, neither used here.
    uvicorn.run(app, host=args.host, port=args.port, reload=False)
