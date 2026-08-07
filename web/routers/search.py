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

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import StreamingResponse

from services import search_service
from services.report_context import ReportContext, build_filters_summary
from services.reports import generate_pdf, generate_docx, generate_xlsx, generate_markdown

from web.dependencies import get_session_state, attach_session_cookie
from web.search_cache import cached_search
from web.session_store import MAX_HISTORY_ENTRIES
from web.search_presentation import (
    STRATEGY_LABELS,
    BUDGET_OPTIONS,
    INDEXING_OPTIONS,
    QUARTILE_OPTIONS,
    SINTA_LEVEL_OPTIONS,
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
        "review_time_options": list(REVIEW_TIME_BANDS.keys()),
    }


def _results_context(session):
    """
    Builds the template context for the results panel from whatever is
    currently in the session — used by every route that renders it
    (initial page load, a new search, pagination, the show-weaker
    toggle, and history rerun), so they can never drift apart.
    """

    all_results = session.get("current_results")

    if all_results is None:
        return {"has_search": False, "history": session["history"]}

    visible_results = filter_visible_results(all_results, session["show_weaker"])
    session["visible_results"] = visible_results

    page_results, page, total_pages = paginate(visible_results, session["page"])
    session["page"] = page

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
    }


@router.get("")
def search_page(request: Request, session=Depends(get_session_state)):
    context = {**_filter_context(), **_results_context(session)}
    return _render(request, "pages/search.html", context, session)


@router.post("")
def run_search(
    request: Request,
    session=Depends(get_session_state),
    title: str = Form(""),
    abstract: str = Form(""),
    keywords: str = Form(""),
    strategy_label: str = Form(...),
    language: str = Form("Any"),
    budget_choice: str = Form("Any"),
    review_time_choice: str = Form("Any"),
    indexing: list[str] = Form([]),
    quartiles: list[str] = Form([]),
    sinta_levels: list[str] = Form([]),
):
    title = title.strip()
    abstract = abstract.strip()

    if not title or not abstract:
        context = {
            **_filter_context(),
            **_results_context(session),
            "warning": "Please enter both a title and an abstract.",
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
            "warning": "Please select at least one journal index before searching.",
        }
        return _render(request, "partials/search_results.html", context, session)

    keyword_list = [k.strip() for k in keywords.replace(";", ",").split(",") if k.strip()]

    resolved_language = None if language == "Any" else language
    free_only, min_budget, max_budget = budget_to_range(budget_choice)
    max_review_weeks = REVIEW_TIME_BANDS[review_time_choice]
    resolved_strategy = STRATEGY_LABELS[strategy_label]

    results = cached_search(
        title=title,
        keywords=keyword_list,
        abstract=abstract,
        language=resolved_language,
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
        language=resolved_language,
        free_only=free_only,
        min_budget=min_budget,
        max_budget=max_budget,
        indexing=indexing or None,
        quartiles=quartiles or None,
        sinta_levels=sinta_levels or None,
        max_review_weeks=max_review_weeks,
    )

    search_meta = {
        "title": title,
        "abstract": abstract,
        "keywords": keyword_list,
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

    context = {**_filter_context(), **_results_context(session)}
    return _render(request, "partials/search_results.html", context, session)


def _build_report_context(search_meta, results):
    return ReportContext(
        title=search_meta.get("title", ""),
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
