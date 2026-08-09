"""
Language switching (#84) -- a session preference, not a URL prefix
(see web/i18n.py for why: "preserve URL and API compatibility"). Plain
POST-redirect-GET, not HTMX: switching language changes strings across
the whole page (nav, footer, and home's content), so a full reload is
the honest thing to do, not a partial swap.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from web.dependencies import get_session_state, attach_session_cookie
from web.i18n import SUPPORTED_LOCALES

router = APIRouter()


@router.post("/locale/{code}")
def set_locale(request: Request, code: str, session=Depends(get_session_state)):
    if code in SUPPORTED_LOCALES:
        session["locale"] = code

    destination = request.headers.get("referer") or "/"
    response = RedirectResponse(url=destination, status_code=303)
    return attach_session_cookie(response, session)
