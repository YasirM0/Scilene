"""
Submission Search — Phase 3 of the v0.2.0 migration.

Every route here goes through services.search_service /
web.search_cache (which itself calls search_service) — never
services.repository or the recommender directly. Presentation-only
logic (option labels, confidence colors, pagination, visible-results
filtering) lives in web.search_presentation, not in these route
functions or in the templates.
"""

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse

from services import search_service
from services.app_info import APP_VERSION
from services.discipline_detection import detect_disciplines
from services.jis_format import serialize_jis, parse_jis_import, InvalidJisFile
from services.report_context import ReportContext, build_filters_summary
from services.reports import generate_pdf, generate_docx, generate_xlsx, generate_markdown

from web.confirmed_tags import add_confirmed_tag, confirmed_tag_values
from web.dependencies import get_session_state, attach_session_cookie
from web.interpreter_presentation import current_suggestions_context
from web.language_presentation import language_form_context
from web.search_cache import cached_search
from web.session_store import MAX_HISTORY_ENTRIES
from web.search_presentation import (
    STRATEGY_LABELS,
    BUDGET_OPTIONS,
    INDEXING_OPTIONS,
    QUARTILE_OPTIONS,
    SINTA_LEVEL_OPTIONS,
    LANGUAGE_OPTIONS,
    REVIEW_TIME_BANDS,
    budget_to_range,
    filter_visible_results,
    paginate,
    build_export_basename,
)
from web.templating import templates

router = APIRouter(prefix="/search")

_EXPORT_GENERATORS = {
    "pdf": (generate_pdf, "application/pdf"),
    "docx": (generate_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xlsx": (generate_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "md": (generate_markdown, "text/markdown"),
}


def _render(request, name, context, session):
    """
    Renders a template AND attaches the session cookie to the actual
    response object being returned — see dependencies.py for why these
    can't be two separate steps (a dependency-injected Response and a
    route's own returned Response are different objects).
    """
    response = templates.TemplateResponse(request=request, name=name, context=context)
    return attach_session_cookie(response, session)


def _filter_context():
    """Static option lists the form/filter templates need — same on every render."""
    return {
        "strategy_labels": list(STRATEGY_LABELS.keys()),
        "budget_options": BUDGET_OPTIONS,
        "indexing_options": INDEXING_OPTIONS,
        "quartile_options": QUARTILE_OPTIONS,
        "sinta_level_options": SINTA_LEVEL_OPTIONS,
        "language_options": LANGUAGE_OPTIONS,
        "review_time_options": list(REVIEW_TIME_BANDS.keys()),
    }


def _interpreter_form_context(session):
    """
    Research Interpreter panel + confirmed-tags state for the initial
    page render (web/routers/interpreter.py owns every subsequent HTMX
    update to this same state) — see web/interpreter_presentation.py.
    """
    return {
        "confirmed_tags": session.get("confirmed_tags", []),
        **current_suggestions_context(session),
    }


def _display_label(abstract, concepts):
    """
    Search history / export reports need a short human-readable label
    for a search that no longer necessarily has a title (v0.2.5 --
    abstract or tags only). Falls back through abstract -> concepts ->
    a plain placeholder; services/report_context.py's own "Untitled
    Search" fallback still applies wherever this ends up empty.
    """
    if abstract:
        return abstract[:80] + ("…" if len(abstract) > 80 else "")
    if concepts:
        shown = ", ".join(concepts[:3])
        return shown + ("…" if len(concepts) > 3 else "")
    return ""


def _results_context(session):
    """
    Builds the template context for the results panel from whatever is
    currently in the session — used by every route that renders it
    (initial page load, a new search, pagination, the show-weaker
    toggle, and history rerun), so they can never drift apart.
    """

    all_results = session.get("current_results")

    if all_results is None:
        return {
            "has_search": False,
            "history": session["history"],
            "compare_ids": session.get("compare_journal_ids", []),
        }

    visible_results = filter_visible_results(all_results, session["show_weaker"])
    session["visible_results"] = visible_results

    page_results, page, total_pages = paginate(visible_results, session["page"])
    session["page"] = page

    # Detected Research Areas (#102) -- real subject-frequency signal
    # over the results already produced, not a fake AI call. Excludes
    # anything already a confirmed search concept, since re-offering a
    # discipline the user already searched with is not new information.
    confirmed_values = confirmed_tag_values(session)
    detected_disciplines = [
        d for d in detect_disciplines(all_results) if d not in confirmed_values
    ]

    return {
        "has_search": True,
        "search_meta": session["search_meta"],
        "total_count": len(all_results),
        "visible_count": len(visible_results),
        "hidden_count": len(all_results) - len(visible_results),
        "show_weaker": session["show_weaker"],
        "page_results": page_results,
        "page": page,
        "total_pages": total_pages,
        "history": session["history"],
        "detected_disciplines": detected_disciplines,
        "compare_ids": session.get("compare_journal_ids", []),
    }


def _execute_search(session, abstract, concepts, strategy_label, resolved_languages,
                     free_only, min_budget, max_budget, indexing, quartiles,
                     sinta_levels, max_review_weeks, resolved_strategy):
    """
    Runs a search and stores everything about it in the session --
    results, display metadata, history, AND the raw parameters
    (`last_search_params`), so a later action that only changes the
    concept list (#102's "refine with detected disciplines") can
    genuinely re-run the same search rather than fake it. Shared by
    run_search() and refine_with_disciplines().
    """

    results = cached_search(
        title="",
        keywords=concepts,
        abstract=abstract,
        languages=resolved_languages,
        free_only=free_only,
        min_budget=min_budget,
        max_budget=max_budget,
        indexing=indexing or None,
        quartiles=quartiles or None,
        sinta_levels=sinta_levels or None,
        max_review_weeks=max_review_weeks,
        strategy=resolved_strategy,
    )

    filters_summary = build_filters_summary(
        languages=resolved_languages,
        free_only=free_only,
        min_budget=min_budget,
        max_budget=max_budget,
        indexing=indexing or None,
        quartiles=quartiles or None,
        sinta_levels=sinta_levels or None,
        max_review_weeks=max_review_weeks,
    )

    search_meta = {
        "display_label": _display_label(abstract, concepts),
        "abstract": abstract,
        "keywords": concepts,
        "strategy_label": strategy_label,
        "filters_summary": filters_summary,
    }

    session["current_results"] = results
    session["search_meta"] = search_meta
    session["show_weaker"] = False
    session["page"] = 1

    session["history"].insert(0, {
        "results": results,
        "search_meta": search_meta,
        "result_count": len(results),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    })
    session["history"] = session["history"][:MAX_HISTORY_ENTRIES]

    session["last_search_params"] = {
        "abstract": abstract,
        "strategy_label": strategy_label,
        "resolved_languages": resolved_languages,
        "free_only": free_only,
        "min_budget": min_budget,
        "max_budget": max_budget,
        "indexing": indexing,
        "quartiles": quartiles,
        "sinta_levels": sinta_levels,
        "max_review_weeks": max_review_weeks,
        "resolved_strategy": resolved_strategy,
    }

    return results


@router.get("")
def search_page(request: Request, session=Depends(get_session_state)):
    context = {
        **_filter_context(),
        **_results_context(session),
        **_interpreter_form_context(session),
        **language_form_context(session),
    }
    return _render(request, "pages/search.html", context, session)


@router.post("")
def run_search(
    request: Request,
    session=Depends(get_session_state),
    abstract: str = Form(""),
    fallback_tags: str = Form(""),
    strategy_label: str = Form(...),
    languages: list[str] = Form([]),
    budget_choice: str = Form("Any"),
    review_time_choice: str = Form("Any"),
    indexing: list[str] = Form([]),
    quartiles: list[str] = Form([]),
    sinta_levels: list[str] = Form([]),
):
    abstract = abstract.strip()

    # Confirmed concepts (accepted Research Interpreter suggestions +
    # anything manually added) and the "no abstract" fallback tags feed
    # the SAME recommender `keywords` list -- the UI doesn't distinguish
    # between them once confirmed (docs/RESEARCH_INTERPRETER.md).
    confirmed_values = confirmed_tag_values(session)
    parsed_fallback = [t.strip() for t in fallback_tags.replace(";", ",").split(",") if t.strip()]
    concepts = confirmed_values + [t for t in parsed_fallback if t not in confirmed_values]

    if not abstract and len(concepts) < 10:
        context = {
            **_filter_context(),
            **_results_context(session),
            **_interpreter_form_context(session),
            "warning": (
                "Please provide an abstract, or at least 10 descriptive tags "
                f"if you don't have one ({len(concepts)} so far)."
            ),
        }
        return _render(request, "partials/search_results.html", context, session)

    if not indexing:
        # Clear any previous results rather than reusing
        # _results_context(session) as-is -- otherwise a prior search's
        # results stay on screen looking like they matched this
        # (invalid) submission. No history entry either: this never
        # ran a real search.
        session["current_results"] = None
        session["visible_results"] = None
        session["search_meta"] = None

        context = {
            **_filter_context(),
            **_results_context(session),
            **_interpreter_form_context(session),
            "warning": "Please select at least one journal index before searching.",
        }
        return _render(request, "partials/search_results.html", context, session)

    resolved_languages = languages or None
    free_only, min_budget, max_budget = budget_to_range(budget_choice)
    max_review_weeks = REVIEW_TIME_BANDS[review_time_choice]
    resolved_strategy = STRATEGY_LABELS[strategy_label]

    results = _execute_search(
        session, abstract, concepts, strategy_label, resolved_languages,
        free_only, min_budget, max_budget, indexing, quartiles,
        sinta_levels, max_review_weeks, resolved_strategy,
    )

    context = {**_filter_context(), **_results_context(session)}
    if not results:
        context["warning"] = (
            "No journals matched your current filters. Try a broader search, "
            "a different budget/language, or fewer indexing/quartile filters."
        )

    return _render(request, "partials/search_results.html", context, session)


@router.post("/refine-with-disciplines")
def refine_with_disciplines(
    request: Request,
    session=Depends(get_session_state),
    disciplines: list[str] = Form([]),
    extra_disciplines: str = Form(""),
):
    """
    #102's "[Edit] -> confirm -> recalculates recommendations using
    the updated disciplines as an additional signal" -- adds the
    user-selected Detected Research Areas (and any manually-typed
    ones -- #102's own "Add missing disciplines", not just remove/
    select from what was auto-detected) to confirmed_tags and
    genuinely re-runs the exact same search (via last_search_params,
    set by _execute_search) with the expanded concept list. The
    traditional recommendation signals are otherwise unchanged; this
    only adds more concepts to the same keyword-matching path every
    manually-typed tag already goes through.
    """

    params = session.get("last_search_params")
    if not params:
        # Nothing to refine -- no search has run yet this session.
        context = {**_filter_context(), **_results_context(session)}
        return _render(request, "partials/search_results.html", context, session)

    for discipline in disciplines:
        add_confirmed_tag(session, discipline, origin="ai")
    extra = [d.strip() for d in extra_disciplines.replace(";", ",").split(",") if d.strip()]
    for discipline in extra:
        add_confirmed_tag(session, discipline, origin="user")

    concepts = confirmed_tag_values(session)  # same values run_search's own concepts computation would produce

    results = _execute_search(
        session, params["abstract"], concepts, params["strategy_label"],
        params["resolved_languages"], params["free_only"], params["min_budget"],
        params["max_budget"], params["indexing"], params["quartiles"],
        params["sinta_levels"], params["max_review_weeks"], params["resolved_strategy"],
    )

    context = {**_filter_context(), **_results_context(session)}
    if not results:
        context["warning"] = (
            "No journals matched your current filters. Try a broader search, "
            "a different budget/language, or fewer indexing/quartile filters."
        )

    return _render(request, "partials/search_results.html", context, session)


@router.get("/results")
def refine_results(request: Request, session=Depends(get_session_state), page: int = 1, show_weaker: str | None = None):
    session["show_weaker"] = show_weaker is not None
    session["page"] = page
    context = {**_filter_context(), **_results_context(session)}
    return _render(request, "partials/search_results.html", context, session)


@router.post("/history/{index}/rerun")
def rerun_history(request: Request, index: int, session=Depends(get_session_state)):
    if 0 <= index < len(session["history"]):
        entry = session["history"][index]
        session["current_results"] = entry["results"]
        session["search_meta"] = entry["search_meta"]
        session["show_weaker"] = False
        session["page"] = 1

    context = {**_filter_context(), **_results_context(session)}
    return _render(request, "partials/search_results.html", context, session)


@router.post("/clear")
def clear_search(request: Request, session=Depends(get_session_state)):
    session["current_results"] = None
    session["visible_results"] = None
    session["search_meta"] = None
    session["show_weaker"] = False
    session["page"] = 1

    # A full reset, not just the results -- otherwise "Clear Search"
    # would leave confirmed tags and interpreter suggestions from the
    # previous search sitting in the form.
    session["confirmed_tags"] = []
    session["interpreter_suggestions"] = []
    session["interpreter_abstract_snapshot"] = None
    session["last_search_params"] = None
    session["detected_language"] = None
    session["language_touched"] = False

    context = {
        **_filter_context(),
        **_results_context(session),
        **language_form_context(session),
        "reset_form": True,
    }
    return _render(request, "partials/search_results.html", context, session)


@router.post("/language-filter/touch")
def touch_language_filter(session=Depends(get_session_state)):
    """
    Fired once (event delegation, see language_filter_card.html's
    wrapping div) whenever any language checkbox changes by hand --
    per #89: "Once the user changes the language filter manually, the
    hint disappears." Doesn't touch which languages are selected,
    only whether the "detected X" hint should still show.
    """
    session["language_touched"] = True
    response = HTMLResponse("")
    return attach_session_cookie(response, session)


def _build_report_context(search_meta, results):
    return ReportContext(
        title=search_meta.get("display_label", ""),
        abstract=search_meta.get("abstract", ""),
        keywords=search_meta.get("keywords", []),
        strategy_label=search_meta.get("strategy_label", ""),
        filters_summary=search_meta.get("filters_summary", []),
        results=results,
    )


@router.get("/export/{fmt}")
def export_results(fmt: str, session=Depends(get_session_state)):
    results = session.get("visible_results") or []
    search_meta = session.get("search_meta") or {}
    basename = build_export_basename(search_meta.get("strategy_label") or "⚖️ Balanced (Recommended)")

    if fmt == "csv":
        data = search_service.export_results_csv(results, context=_build_report_context(search_meta, results))
        media_type = "text/csv"
    elif fmt == "jis":
        # Portable Search Session (#91) -- unlike every other format
        # here, this isn't a report OF the results, it's the search
        # ITSELF (params + tags), reopenable via /search/import-jis.
        data = serialize_jis(session, APP_VERSION)
        media_type = "application/json"
    elif fmt in _EXPORT_GENERATORS:
        generator, media_type = _EXPORT_GENERATORS[fmt]
        data = generator(_build_report_context(search_meta, results))
    else:
        data, media_type = b"Unknown export format", "text/plain"

    response = StreamingResponse(
        BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{basename}.{fmt}"'},
    )
    return attach_session_cookie(response, session)


@router.post("/import-jis")
def import_jis(request: Request, file: UploadFile = File(...), session=Depends(get_session_state)):
    """
    Portable Search Sessions (#91) -- the counterpart to /export/jis.
    Always genuinely RE-RUNS the search against the live database
    (via _execute_search, the exact function a manual search calls)
    rather than replaying the file's results_snapshot -- a session
    opened days later or on another device should reflect the current
    database, not a stale copy of it.
    """
    raw = file.file.read()

    try:
        search = parse_jis_import(raw)
    except InvalidJisFile as exc:
        context = {
            **_filter_context(),
            **_results_context(session),
            "warning": f"Couldn't load this .jis file: {exc}",
        }
        return _render(request, "partials/search_results.html", context, session)

    indexing = search.get("indexing") or []
    if not indexing:
        context = {
            **_filter_context(),
            **_results_context(session),
            "warning": "This .jis file has no journal index selected — nothing to search with.",
        }
        return _render(request, "partials/search_results.html", context, session)

    strategy_label = search.get("strategy_label")
    if strategy_label not in STRATEGY_LABELS:
        strategy_label = "⚖️ Balanced (Recommended)"

    abstract = (search.get("abstract") or "").strip()
    # Imported tags aren't fresh Scilene suggestions -- closest fit is
    # "user" (a prior session's own confirmed concepts), not "ai".
    session["confirmed_tags"] = []
    for tag in search.get("confirmed_tags") or []:
        add_confirmed_tag(session, str(tag), origin="user")
    confirmed = confirmed_tag_values(session)

    _execute_search(
        session, abstract, confirmed, strategy_label,
        search.get("languages"),
        bool(search.get("free_only")),
        search.get("min_budget"),
        search.get("max_budget"),
        indexing,
        search.get("quartiles") or [],
        search.get("sinta_levels") or [],
        search.get("max_review_weeks"),
        STRATEGY_LABELS[strategy_label],
    )

    context = {
        **_filter_context(),
        **_results_context(session),
        **_interpreter_form_context(session),
        **language_form_context(session),
    }
    return _render(request, "partials/search_results.html", context, session)
