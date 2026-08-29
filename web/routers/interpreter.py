"""
Research Interpreter interaction (docs/RESEARCH_INTERPRETER.md).

Every route here just reads/writes session state and re-renders
partials/interpreter_panel.html (or confirmed_tags.html) -- no
JavaScript state machine, HTMX round-trips ARE the state transitions.
services/research_interpreter.py supplies the (placeholder) suggested
values; nothing here ever touches services/recommender.py.
"""

from fastapi import APIRouter, Depends, Form, Request

from services.abstract_validation import is_too_short
from services.language_detection import detect_language
from services.research_interpreter import suggest_concepts, next_suggestion, CATEGORIES
from web.confirmed_tags import add_confirmed_tag
from web.dependencies import get_session_state, attach_session_cookie
from web.interpreter_presentation import current_suggestions_context
from web.language_presentation import language_form_context
from web.templating import templates

router = APIRouter(prefix="/search")


def _render_panel(request, session, extra_context=None, has_abstract=None):
    context = dict(extra_context or {})
    if has_abstract is not None:
        # #143 follow-up -- Search Concepts only appears once there's
        # something for it to hold: the abstract currently has text,
        # OR there are already-confirmed tags from earlier this
        # session (which must stay visible even if the abstract was
        # since cleared back to empty).
        context["concepts_section_oob"] = {
            "visible": has_abstract or bool(session.get("confirmed_tags")),
            "confirmed_tags": session.get("confirmed_tags", []),
            "field_examples": context.get("field_examples", []),
        }
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

    has_abstract = bool(abstract)

    if not abstract:
        session["interpreter_suggestions"] = []
        session["interpreter_abstract_snapshot"] = None
        session["interpreter_editing_category"] = None
        context = {"state": "empty"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session, request.state.locale)
        return _render_panel(request, session, context, has_abstract=has_abstract)

    if is_too_short(abstract):
        # No snapshot saved -- once the abstract clears the minimum,
        # this is treated as a genuine first run, not a "changed" one.
        session["interpreter_suggestions"] = []
        session["interpreter_abstract_snapshot"] = None
        session["interpreter_editing_category"] = None
        context = {"state": "too_short"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session, request.state.locale)
        return _render_panel(request, session, context, has_abstract=has_abstract)

    snapshot = session.get("interpreter_abstract_snapshot")

    if snapshot is None:
        # First run for this abstract.
        session["interpreter_suggestions"] = suggest_concepts(abstract)
        session["interpreter_abstract_snapshot"] = abstract
        session["interpreter_editing_category"] = None
        context = {"state": "analyzing"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session, request.state.locale)
        return _render_panel(request, session, context, has_abstract=has_abstract)

    if abstract != snapshot:
        # Existing suggestions, but the text has moved on -- don't
        # silently regenerate (would discard "suggest another" choices
        # the user already made), ask first.
        context = {"state": "changed_notice"}
        if language_changed:
            context["language_card_oob"] = language_form_context(session, request.state.locale)
        return _render_panel(request, session, context, has_abstract=has_abstract)

    context = current_suggestions_context(session)
    if language_changed:
        context["language_card_oob"] = language_form_context(session, request.state.locale)
    return _render_panel(request, session, context, has_abstract=has_abstract)


@router.get("/interpret/reveal")
def interpret_reveal(request: Request, session=Depends(get_session_state)):
    # has_abstract=True -- this route only ever runs as the "analyzing"
    # state's own auto-follow-up (interpreter_panel.html's hx-trigger),
    # which only fires when an abstract was actually submitted. Needs
    # to refresh the tag-box's OOB section too, not just this panel --
    # the "analyzing" state's own render couldn't yet know
    # field_of_study_examples()'s real result (detection hadn't run),
    # so it rendered the no-examples helper text; this is the first
    # response that can show the real one.
    return _render_panel(request, session, current_suggestions_context(session), has_abstract=True)


@router.post("/interpret/refresh")
def interpret_refresh(request: Request, abstract: str = Form(""), session=Depends(get_session_state)):
    abstract = abstract.strip()
    if is_too_short(abstract):
        session["interpreter_suggestions"] = []
        session["interpreter_abstract_snapshot"] = None
        session["interpreter_editing_category"] = None
        return _render_panel(request, session, {"state": "too_short"})
    session["interpreter_suggestions"] = suggest_concepts(abstract)
    session["interpreter_abstract_snapshot"] = abstract
    session["interpreter_editing_category"] = None
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
            abstract = session.get("interpreter_abstract_snapshot") or ""
            tag["value"] = next_suggestion(category, tag["value"], abstract)
            tag["cycled"] = True
    session["interpreter_editing_category"] = None
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/accept/{category}")
def interpret_accept(request: Request, category: str, session=Depends(get_session_state)):
    if category in CATEGORIES:
        tag = _find_suggestion(session, category)
        if tag is not None:
            session["interpreter_suggestions"] = [
                t for t in session["interpreter_suggestions"] if t["category"] != category
            ]
            add_confirmed_tag(session, tag["value"], origin="ai")
    session["interpreter_editing_category"] = None

    context = current_suggestions_context(session)
    context["confirmed_tags_oob"] = session["confirmed_tags"]
    return _render_panel(request, session, context)


@router.post("/interpret/remove/{category}")
def interpret_remove(request: Request, category: str, session=Depends(get_session_state)):
    if category in CATEGORIES:
        session["interpreter_suggestions"] = [
            t for t in session["interpreter_suggestions"] if t["category"] != category
        ]
    session["interpreter_editing_category"] = None
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/edit-start/{category}")
def interpret_edit_start(request: Request, category: str, session=Depends(get_session_state)):
    """
    #110 "✏ Edit" -- swaps one suggestion row into an inline text
    input (see interpreter_panel.html's editing_category branch)
    instead of duplicating suggest_concepts()' pool logic here; the
    row's current value is just prefilled as the input's starting text.
    """
    if category in CATEGORIES and _find_suggestion(session, category) is not None:
        session["interpreter_editing_category"] = category
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/edit-cancel")
def interpret_edit_cancel(request: Request, session=Depends(get_session_state)):
    session["interpreter_editing_category"] = None
    return _render_panel(request, session, current_suggestions_context(session))


@router.post("/interpret/edit-save/{category}")
def interpret_edit_save(request: Request, category: str, value: str = Form(""), session=Depends(get_session_state)):
    value = value.strip()
    if category in CATEGORIES and value:
        tag = _find_suggestion(session, category)
        if tag is not None:
            tag["value"] = value
            # Same reasoning as suggest-another: no longer the pool's
            # placeholder default, so "Remove" becomes available too.
            tag["cycled"] = True
    session["interpreter_editing_category"] = None
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


@router.post("/tags/add")
def add_tag(request: Request, value: str = Form(""), session=Depends(get_session_state)):
    """
    #139 -- the "Add a tag..." field below AI suggestions. Always
    origin="user": this is the one path that's genuinely just the
    researcher's own words, not something Scilene proposed first.
    """
    add_confirmed_tag(session, value, origin="user")

    response = templates.TemplateResponse(
        request=request,
        name="partials/tag_added.html",
        context={"tags": session["confirmed_tags"]},
    )
    return attach_session_cookie(response, session)
