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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from services.app_info import APP_NAME, APP_VERSION
from web.config import get_settings
from web.routers import home, pages, search, interpreter, enrichment

settings = get_settings()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    debug=settings.debug,
)

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
