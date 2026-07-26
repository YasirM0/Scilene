"""
Placeholder routes for pages not yet built out (Search is Phase 3;
Academy and Documentation have no target milestone yet). Each is a
plain, explicit route rendering the shared coming_soon.html template
with page-specific text — one function per route rather than a
generic/looped registration, so each is easy to find and replace with
real content on its own later.
"""

from fastapi import APIRouter, Request

from web.templating import templates

router = APIRouter()


@router.get("/search")
def search_placeholder(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/coming_soon.html",
        context={
            "page_title": "Submission Search",
            "page_description": (
                "The full journal search experience is still on the Streamlit "
                "app while it's migrated here in a later phase of the v0.2.0 "
                "migration."
            ),
        },
    )


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
