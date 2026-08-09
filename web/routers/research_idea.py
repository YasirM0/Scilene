"""
Research Idea Assistant (#85).

Not a second search workflow -- an AI-assisted entry point that feeds
the SAME Submission Search page every other search already uses (the
issue's "Canonical Search Principle"). AI only ever prepares input
tags for the user to review and edit; it never sees or influences a
recommendation. See services/ai_provider.py's generate_search_inputs()
for what "AI generates" honestly means here (restructuring the user's
own words, not writing new prose -- no concrete generative provider is
configured anywhere in this app yet).

Deliberately keywords-only, not abstract-generation, even though the
underlying AIResponse also carries a title/abstract (see
generate_search_inputs()'s docstring): #110, implemented after #85 and
authoritative on the Submission Search page's actual shape, says a
user without an abstract should provide "at least 10 descriptive
tags... No abstract generation is required." So "Continue to Search"
here feeds session["confirmed_tags"] -- the exact tag-based path #110
describes -- never a pre-filled abstract. A user WITH a real abstract
should paste it directly on the Submission Search page; this entry
point is specifically for the no-abstract-yet case #110 already
designed for.
"""

from fastapi import APIRouter, Depends, Form, Request

from services.ai_provider import get_default_provider
from web.confirmed_tags import add_confirmed_tag
from web.dependencies import get_session_state, attach_session_cookie
from web.templating import templates

router = APIRouter(prefix="/research-idea")


def _render(request, name, context):
    return templates.TemplateResponse(request=request, name=name, context=context)


@router.get("/form")
def reset_form(request: Request):
    """Plain re-render of the idea-input form -- "← Start over" from
    the review step, no generation involved."""
    return _render(request, "partials/research_idea_form.html", {})


@router.post("/generate")
def generate(request: Request, idea: str = Form("")):
    response = get_default_provider().generate_search_inputs(idea)

    if not response.ok:
        return _render(request, "partials/research_idea_result.html", {
            "ok": False,
            "error": response.error,
            "idea": idea,
        })

    return _render(request, "partials/research_idea_result.html", {
        "ok": True,
        "keywords": response.data["keywords"],
    })


@router.post("/continue")
def continue_to_search(
    request: Request,
    keywords: str = Form(""),
    session=Depends(get_session_state),
):
    """
    Carries the (possibly user-edited) keywords into
    session["confirmed_tags"] -- the exact same list
    interpret_accept() appends accepted Research Interpreter
    suggestions to (web/routers/interpreter.py), so the recommender
    receives identical input either way, per #85's own Design
    Principles. No abstract is generated or carried anywhere -- see
    this module's docstring for why (#110 supersedes that part of
    #85's original design).
    """
    parsed_keywords = [k.strip() for k in keywords.replace(";", ",").split(",") if k.strip()]

    for keyword in parsed_keywords:
        add_confirmed_tag(session, keyword, origin="ai")

    response = templates.TemplateResponse(
        request=request, name="partials/empty.html", context={}
    )
    response.headers["HX-Redirect"] = "/search"
    return attach_session_cookie(response, session)
