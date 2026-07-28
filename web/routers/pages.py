"""
Academy has real content (ported from Streamlit's own Publication
Academy page — it was never actually a bare placeholder there either,
just self-labeled "under development" while already containing four
sections of real reference content). Documentation has no Streamlit
equivalent to port — see docs/WEB_MIGRATION.md for why it stays a
placeholder rather than getting invented content.
"""

from fastapi import APIRouter, Request

from web.templating import templates

router = APIRouter()


@router.get("/academy")
def academy(request: Request):
    return templates.TemplateResponse(request=request, name="pages/academy.html", context={})


@router.get("/documentation")
def documentation_placeholder(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/coming_soon.html",
        context={
            "page_title": "Documentation",
            "page_description": (
                "User-facing documentation for Journal Intelligence is planned "
                "for a future milestone."
            ),
        },
    )
