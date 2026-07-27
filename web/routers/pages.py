"""
Placeholder routes for pages not yet built out (Academy and
Documentation have no target milestone yet). Submission Search moved
to web/routers/search.py as of Phase 3 — it's real now, not a
placeholder, so it no longer lives here.
"""

from fastapi import APIRouter, Request

from web.templating import templates

router = APIRouter()


@router.get("/academy")
def academy_placeholder(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/coming_soon.html",
        context={
            "page_title": "Publication Academy",
            "page_description": (
                "Educational content on academic publishing is planned for a "
                "future milestone."
            ),
        },
    )


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
