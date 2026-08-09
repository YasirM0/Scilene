"""
Documentation has no Streamlit equivalent to port — see
docs/WEB_MIGRATION.md for why it stays a placeholder rather than
getting invented content. (Publication Academy used to live here too;
removed in v0.2.5 -- see docs/WEB_MIGRATION.md's update note.)
"""

import logging

from fastapi import APIRouter, Request

from services.app_info import APP_NAME
from services.search_service import get_dashboard_stats
from web.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/about")
def about(request: Request):
    return templates.TemplateResponse(request=request, name="pages/about.html", context={})


@router.get("/statistics")
def statistics(request: Request):
    """Statistics Dashboard (#60) -- read-only, no session state."""
    try:
        stats = get_dashboard_stats()
    except Exception:
        logger.exception("Could not reach the database for the statistics dashboard")
        stats = None

    return templates.TemplateResponse(request=request, name="pages/statistics.html", context={"stats": stats})


@router.get("/documentation")
def documentation_placeholder(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/coming_soon.html",
        context={
            "page_title": "Documentation",
            "page_description": (
                f"User-facing documentation for {APP_NAME} is planned "
                "for a future milestone."
            ),
        },
    )
