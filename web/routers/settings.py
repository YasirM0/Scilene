"""
Settings page (#108) -- currently exactly one real preference: whether
online metadata enrichment (#107, OpenAlex/Crossref) is offered at
all. Session-scoped, same storage model as show_weaker/confirmed_tags
(web/session_store.py) -- not a durable account setting, since this
app has no accounts.
"""

from fastapi import APIRouter, Depends, Form, Request

from web.dependencies import get_session_state, attach_session_cookie
from web.templating import templates

router = APIRouter()


def _render(request, session, saved=False):
    response = templates.TemplateResponse(
        request=request,
        name="pages/settings.html",
        context={
            "enrichment_enabled": session["enrichment_enabled"],
            "saved": saved,
        },
    )
    return attach_session_cookie(response, session)


@router.get("/settings")
def settings_page(request: Request, session=Depends(get_session_state)):
    return _render(request, session)


@router.post("/settings")
def update_settings(
    request: Request,
    enrichment_enabled: str | None = Form(None),
    session=Depends(get_session_state),
):
    session["enrichment_enabled"] = enrichment_enabled is not None
    return _render(request, session, saved=True)
