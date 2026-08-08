"""
Research Idea Assistant (#85).

Not a second search workflow -- an AI-assisted entry point that feeds
the SAME Submission Search page every other search already uses (the
issue's "Canonical Search Principle"). AI only ever prepares input
text/tags for the user to review and edit; it never sees or influences
a recommendation. See services/ai_provider.py's generate_search_inputs()
for what "AI generates" honestly means here (restructuring the user's
own words, not writing new prose -- no concrete generative provider is
configured anywhere in this app yet).
"""

from fastapi import APIRouter, Depends, Form, Request

from services.ai_provider import get_default_provider
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
        "title": response.data["title"],
        "abstract": response.data["abstract"],
        "keywords": response.data["keywords"],
    })


@router.post("/continue")
def continue_to_search(
    request: Request,
    abstract: str = Form(""),
    keywords: str = Form(""),
    session=Depends(get_session_state),
):
    """
    Carries the (possibly user-edited) abstract + keywords into the
    SAME session fields a manual search already populates --
    confirmed_tags is exactly the list interpret_accept() appends
    accepted Research Interpreter suggestions to (web/routers/interpreter.py),
    so the recommender receives identical input either way, per the
    issue's Design Principles. `title` isn't carried anywhere: the
    Submission Search page (v0.2.5's redesign, #110) has no title
    field at all, only abstract + tags -- the idea's first sentence is
    already the abstract's own opening line, so nothing is lost.
    """
    abstract = abstract.strip()
    parsed_keywords = [k.strip() for k in keywords.replace(";", ",").split(",") if k.strip()]

    confirmed = session.get("confirmed_tags", [])
    for keyword in parsed_keywords:
        if keyword not in confirmed:
            confirmed.append(keyword)
    session["confirmed_tags"] = confirmed

    session["prefill_abstract"] = abstract or None

    response = templates.TemplateResponse(
        request=request, name="partials/empty.html", context={}
    )
    response.headers["HX-Redirect"] = "/search"
    return attach_session_cookie(response, session)
