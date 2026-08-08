"""
Research Interpreter interaction (docs/RESEARCH_INTERPRETER.md).

Every route here just reads/writes session state and re-renders
partials/interpreter_panel.html (or confirmed_tags.html) -- no
JavaScript state machine, HTMX round-trips ARE the state transitions.
services/research_interpreter.py supplies the (placeholder) suggested
values; nothing here ever touches services/recommender.py.
"""

from fastapi import APIRouter, Depends, Form, Request

from services.language_detection import detect_language
from services.research_interpreter import suggest_concepts, next_suggestion, CATEGORIES
from web.dependencies import get_session_state, attach_session_cookie
from web.interpreter_presentation import current_suggestions_context
from web.language_presentation import language_form_context
from web.templating import templates

router = APIRouter(prefix="/search")


def _render_panel(request, session, extra_context=None):
    context = dict(extra_context or {})
    response = templates.TemplateResponse(
        request=request, name="partials/interpreter_panel.html", context=context
    )
    return attach_session_cookie(response, session)


def _find_suggestion(session, category):
    for tag in session.get("interpreter_suggestions") or []:
        if tag["category"] == category:
            return tag
    return None


def _update_detected_language(session, abstract):
    """
    Runs on every /search/interpret call (abstract blur/change), same
    trigger the suggestion logic already uses -- one round trip covers
    both (#89), rather than a second competing HTMX request on the
    same textarea. Only touches session state (and so only needs an
    OOB re-render) when the detected language actually changed; a
    redundant re-check of unchanged text is a no-op.
    """
    new_detected = detect_language(abstract)
    if new_detected == session.get("detected_language"):
        return False

    session["detected_language"] = new_detected
    session["language_touched"] = False  # a genuinely new abstract earns a fresh hint
    return True


@router.post("/interpret")
def interpret(request: Request, abstract: str = Form(""), session=Depends(get_session_state)):
    abstract = abstract.strip()

    language_changed = _update_detected_language(session, abstract)

    if not abstract:
        session["interpreter_suggestions"] = []
        session["interpreter_abstract_snapshot"] = None
        context = {"state": "empty"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session)
        return _render_panel(request, session, context)

    snapshot = session.get("interpreter_abstract_snapshot")

    if snapshot is None:
        # First run for this abstract.
        session["interpreter_suggestions"] = suggest_concepts(abstract)
        session["interpreter_abstract_snapshot"] = abstract
        context = {"state": "analyzing"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session)
        return _render_panel(request, session, context)

    if abstract != snapshot:
        # Existing suggestions, but the text has moved on -- don't
        # silently regenerate (would discard "suggest another" choices
        # the user already made), ask first.
        context = {"state": "changed_notice"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session)
        return _render_panel(request, session, context)

    context = current_suggestions_context(session)
    if language_changed:
        context["language_card_oob"] = language_form_context(session)
    return _render_panel(request, session, context)


@router.get("/interpret/reveal")
def interpret_reveal(request: Request, session=Depends(get_session_state)):
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/refresh")
def interpret_refresh(request: Request, abstract: str = Form(""), session=Depends(get_session_state)):
    abstract = abstract.strip()
    session["interpreter_suggestions"] = suggest_concepts(abstract)
    session["interpreter_abstract_snapshot"] = abstract
    return _render_panel(request, session, {"state": "analyzing"})


@router.post("/interpret/keep")
def interpret_keep(request: Request, abstract: str = Form(""), session=Depends(get_session_state)):
    session["interpreter_abstract_snapshot"] = abstract.strip()
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/suggest-another/{category}")
def interpret_suggest_another(request: Request, category: str, session=Depends(get_session_state)):
    if category in CATEGORIES:
        tag = _find_suggestion(session, category)
        if tag is not None:
            tag["value"] = next_suggestion(category, tag["value"])
            tag["cycled"] = True
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/accept/{category}")
def interpret_accept(request: Request, category: str, session=Depends(get_session_state)):
    if category in CATEGORIES:
        tag = _find_suggestion(session, category)
        if tag is not None:
            session["interpreter_suggestions"] = [
                t for t in session["interpreter_suggestions"] if t["category"] != category
            ]
            if tag["value"] not in session["confirmed_tags"]:
                session["confirmed_tags"].append(tag["value"])

    context = current_suggestions_context(session)
    context["confirmed_tags_oob"] = session["confirmed_tags"]
    return _render_panel(request, session, context)


@router.post("/interpret/remove/{category}")
def interpret_remove(request: Request, category: str, session=Depends(get_session_state)):
    if category in CATEGORIES:
        session["interpreter_suggestions"] = [
            t for t in session["interpreter_suggestions"] if t["category"] != category
        ]
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/tags/remove/{index}")
def remove_confirmed_tag(request: Request, index: int, session=Depends(get_session_state)):
    tags = session["confirmed_tags"]
    if 0 <= index < len(tags):
        tags.pop(index)

    response = templates.TemplateResponse(
        request=request, name="partials/confirmed_tags_standalone.html", context={"tags": tags}
    )
    return attach_session_cookie(response, session)
