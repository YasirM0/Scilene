"""
Homepage route.

Goes through services.search_service (not services.repository
directly) for its statistics — "UI -> service layer -> repository ->
database" is the preferred flow so the UI never needs to know it's
SQLite underneath, and any future change to how stats are computed or
cached happens in one place.
"""

import logging

from fastapi import APIRouter, Request

from services.search_service import get_database_stats
from web.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def home(request: Request):

    try:
        stats = get_database_stats()
    except Exception:
        logger.exception("Could not reach the database for homepage stats")
        stats = None

    return templates.TemplateResponse(
        request=request,
        name="pages/home.html",
        context={"stats": stats},
    )
