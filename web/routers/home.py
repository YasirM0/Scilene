"""
Placeholder homepage route (Phase 1 of the v0.2.0 migration).

Deliberately calls into services.repository — a real backend call, not
just static HTML — so this page actually proves the FastAPI app can use
the same core the Streamlit app uses, not just that Jinja2 can render a
template. No search/recommendation logic here yet; that's a later phase.
"""

import logging

from fastapi import APIRouter, Request

from services.repository import count_journals
from web.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def home(request: Request):

    try:
        journal_count = count_journals()
    except Exception:
        logger.exception("Could not reach the database for the journal count")
        journal_count = None

    return templates.TemplateResponse(
        request=request,
        name="pages/home.html",
        context={"journal_count": journal_count},
    )
