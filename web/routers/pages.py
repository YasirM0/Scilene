"""
Publication Academy used to live here too; removed in v0.2.5 -- see
docs/WEB_MIGRATION.md's update note. The Documentation placeholder
route that used to live here was removed once real documentation
(README, docs/) became the answer -- see nav_links in
web/templating.py.
"""

import logging

from fastapi import APIRouter, Request

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
