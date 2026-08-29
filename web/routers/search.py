"""
Submission Search — Phase 3 of the v0.2.0 migration.

Every route here goes through services.search_service /
web.search_cache (which itself calls search_service) — never
services.repository or the recommender directly. Presentation-only
logic (option labels, confidence colors, pagination, visible-results
filtering) lives in web.search_presentation, not in these route
functions or in the templates.

One deliberate exception: POST /search/semantic (#143) calls
services.semantic_search directly, bypassing search_service/the
recommender entirely — a genuinely separate, opt-in ranking strategy,
not a variant of the deterministic pipeline every other route here
goes through.
"""

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse

from services import search_service, semantic_search
from services.app_info import APP_VERSION
from services.discipline_detection import detect_disciplines
from services.query_translator import translate_query, ArabicNotSupportedOnline
from services.sls_format import serialize_sls, parse_sls_import, InvalidSlsFile
from services.report_context import ReportContext, build_filters_summary
from services.reports import generate_pdf, generate_docx, generate_xlsx, generate_markdown

from web.confirmed_tags import add_confirmed_tag, confirmed_tag_values
from web.dependencies import get_session_state, attach_session_cookie
from web.i18n import t
from web.interpreter_presentation import current_suggestions_context
from web.filter_defaults import default_indexing, default_sinta_levels
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
    MIN_FALLBACK_TAGS,
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


def _filter_context(locale):
    """
    Static option lists the form/filter templates need, plus the
    locale-aware smart defaults (#143) for a FRESH render -- initial
    page load or Clear Search, the only two places selections aren't
    just whatever's already sitting in the DOM. `show_quartile_filter`
    / `show_sinta_filter` mirror multiselect.js's own client-side
    syncIndexGatedFilters() gating for the very first paint (before
    any JS has run), so the two never disagree about whether a
    Scopus/WoS-only or SINTA-only reader sees a filter that can't
    possibly apply to anything they picked.
    """
    selected_indexing = default_indexing(locale)
    selected_sinta_levels = default_sinta_levels(locale) if "SINTA" in selected_indexing else []
    return {
        "strategy_labels": list(STRATEGY_LABELS.keys()),
        "budget_options": BUDGET_OPTIONS,
        "indexing_options": INDEXING_OPTIONS,
        "selected_indexing": selected_indexing,
        "quartile_options": QUARTILE_OPTIONS,
        "sinta_level_options": SINTA_LEVEL_OPTIONS,
        "selected_sinta_levels": selected_sinta_levels,
        "show_quartile_filter": any(v in selected_indexing for v in ("Scopus", "Web of Science")),
        "show_sinta_filter": "SINTA" in selected_indexing,
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


# How many results the semantic path returns -- generous enough that
# pagination (10/page, web.search_presentation.PAGE_SIZE) has several
# pages to work with, small enough that ranking/hydrating stays fast.
# No filter parameters yet (#143's first, deliberately minimal cut of
# this opt-in path) -- see services/semantic_search.py's search()
# docstring.
SEMANTIC_TOP_N = 40


def _execute_semantic_search(session, query_text, display_label, languages=None, free_only=False,
                              min_budget=None, max_budget=None, indexing=None, quartiles=None,
                              sinta_levels=None, max_review_weeks=None):
    """
    services/semantic_search.py's counterpart to _execute_search()
    above -- same session-state contract (current_results/search_meta/
    history), so _results_context() and everything downstream of it
    (pagination, export, the show-weaker-matches toggle, journal_card.html)
    work completely unchanged for either search path. `last_search_params`
    stays None here on purpose: #102's "refine with detected disciplines"
    re-runs a search by replaying recommender-specific parameters this
    path doesn't have, so that feature is simply unavailable on a
    semantic-search results set rather than faked.

    Filters (#144) use the exact same parameters/semantics as
    _execute_search()'s own filters -- see services.semantic_search
    .search()'s own docstring for how they're applied (masking the
    corpus before ranking, not the results after).
    """
    results = semantic_search.search(
        query_text, top_n=SEMANTIC_TOP_N, languages=languages, free_only=free_only,
        min_budget=min_budget, max_budget=max_budget, indexing=indexing,
        quartiles=quartiles, sinta_levels=sinta_levels, max_review_weeks=max_review_weeks,
    )

    search_meta = {
        "display_label": display_label,
        "abstract": query_text,
        "keywords": [],
        "strategy_label": "✨ AI Semantic Match (Experimental)",
        "filters_summary": build_filters_summary(
            languages=languages, free_only=free_only, min_budget=min_budget, max_budget=max_budget,
            indexing=indexing, quartiles=quartiles, sinta_levels=sinta_levels, max_review_weeks=max_review_weeks,
        ),
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
    session["last_search_params"] = None

    return results


@router.post("/semantic")
def run_semantic_search(
    request: Request,
    session=Depends(get_session_state),
    abstract: str = Form(""),
    languages: list[str] = Form([]),
    budget_choice: str = Form("Any"),
    review_time_choice: str = Form("Any"),
    indexing: list[str] = Form([]),
    quartiles: list[str] = Form([]),
    sinta_levels: list[str] = Form([]),
):
    """
    #143 -- the opt-in "✨ Try AI Semantic Search" path
    (web/templates/pages/search.html), a second submit button in the
    same form with its own hx-post overriding the form's default.
    Reads the same abstract field and Search Concepts tags every other
    search route does; the actual ranking comes from
    services/semantic_search.py instead of the recommender.

    #144 -- reads the SAME filter fields the button's enclosing <form>
    already carries for the deterministic /search route (this button
    has no hx-include of its own, so htmx's default "closest form"
    inclusion already sends them; they were just ignored here before).
    Unlike /search, an empty `indexing` is NOT treated as an invalid
    submission -- filters are optional narrowing on top of semantic
    ranking, not a required selection the way the deterministic path
    requires at least one indexing source.
    """
    abstract = abstract.strip()
    concepts = confirmed_tag_values(session)

    if not abstract and len(concepts) < MIN_FALLBACK_TAGS:
        context = {
            **_filter_context(request.state.locale),
            **_results_context(session),
            **_interpreter_form_context(session),
            "warning": t(
                "warning.abstract_or_tags_required", request.state.locale,
                count=len(concepts), min=MIN_FALLBACK_TAGS,
            ),
        }
        return _render(request, "partials/search_results.html", context, session)

    query_text = abstract
    if concepts:
        query_text = f"{abstract} {', '.join(concepts)}".strip()

    try:
        query_text, _ = translate_query(query_text)
    except ArabicNotSupportedOnline as e:
        context = {
            **_filter_context(request.state.locale),
            **_results_context(session),
            "warning": str(e),
            "warning_rtl": True,
        }
        return _render(request, "partials/search_results.html", context, session)

    resolved_languages = languages or None
    free_only, min_budget, max_budget = budget_to_range(budget_choice)
    max_review_weeks = REVIEW_TIME_BANDS[review_time_choice]

    results = _execute_semantic_search(
        session, query_text, _display_label(abstract, concepts), languages=resolved_languages,
        free_only=free_only, min_budget=min_budget, max_budget=max_budget, indexing=indexing or None,
        quartiles=quartiles or None, sinta_levels=sinta_levels or None, max_review_weeks=max_review_weeks,
    )

    context = {**_filter_context(request.state.locale), **_results_context(session)}
    if not results:
        context["warning"] = t("warning.no_results", request.state.locale)

    return _render(request, "partials/search_results.html", context, session)


@router.get("")
def search_page(request: Request, mode: str = "manuscript", session=Depends(get_session_state)):
    """
    `mode` (#143) is a pure GET-time presentation flag, not session
    state -- it only decides whether search_form.html shows the
    abstract field or skips straight to tag entry (the homepage's two
    entry buttons set it: "I have a manuscript" -> default/omitted,
    "I only have a research idea" -> ?mode=idea, same for the Research
    Idea modal's "Continue to Search" redirect in
    web/routers/research_idea.py). run_search() below doesn't care
    which mode the page was in -- it just processes whatever fields
    are actually present in the submitted form.
    """
    if mode not in ("manuscript", "idea"):
        mode = "manuscript"
    session["search_mode"] = mode
    context = {
        **_filter_context(request.state.locale),
        **_results_context(session),
        **_interpreter_form_context(session),
        **language_form_context(session, request.state.locale),
        "mode": mode,
        "min_tags": MIN_FALLBACK_TAGS,
    }
    return _render(request, "pages/search.html", context, session)


@router.post("")
def run_search(
    request: Request,
    session=Depends(get_session_state),
    abstract: str = Form(""),
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
    # anything manually added via the Search Concepts tag builder) are
    # the recommender's `keywords` list -- one mechanism regardless of
    # whether the page is in manuscript or idea mode (#143 folded the
    # old separate "10-tag fallback textarea" into this same tag
    # builder rather than keeping two ways to add a tag on one page;
    # see docs/RESEARCH_INTERPRETER.md).
    concepts = confirmed_tag_values(session)

    if not abstract and len(concepts) < MIN_FALLBACK_TAGS:
        context = {
            **_filter_context(request.state.locale),
            **_results_context(session),
            **_interpreter_form_context(session),
            "warning": t(
                "warning.abstract_or_tags_required", request.state.locale,
                count=len(concepts), min=MIN_FALLBACK_TAGS,
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
            **_filter_context(request.state.locale),
            **_results_context(session),
            **_interpreter_form_context(session),
            "warning": t("warning.no_index_selected", request.state.locale),
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

    context = {**_filter_context(request.state.locale), **_results_context(session)}
    if not results:
        context["warning"] = t("warning.no_results", request.state.locale)

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
        context = {**_filter_context(request.state.locale), **_results_context(session)}
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

    context = {**_filter_context(request.state.locale), **_results_context(session)}
    if not results:
        context["warning"] = t("warning.no_results", request.state.locale)

    return _render(request, "partials/search_results.html", context, session)


@router.get("/results")
def refine_results(request: Request, session=Depends(get_session_state), page: int = 1, show_weaker: str | None = None):
    session["show_weaker"] = show_weaker is not None
    session["page"] = page
    context = {**_filter_context(request.state.locale), **_results_context(session)}
    return _render(request, "partials/search_results.html", context, session)


@router.post("/history/{index}/rerun")
def rerun_history(request: Request, index: int, session=Depends(get_session_state)):
    if 0 <= index < len(session["history"]):
        entry = session["history"][index]
        session["current_results"] = entry["results"]
        session["search_meta"] = entry["search_meta"]
        session["show_weaker"] = False
        session["page"] = 1

    context = {**_filter_context(request.state.locale), **_results_context(session)}
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
        **_filter_context(request.state.locale),
        **_results_context(session),
        **language_form_context(session, request.state.locale),
        "mode": session.get("search_mode", "manuscript"),
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
    elif fmt == "sls":
        # Portable Search Session (#91, .sls since #136) -- unlike
        # every other format here, this isn't a report OF the results,
        # it's the search ITSELF (params + tags), reopenable via
        # /search/import-sls.
        data = serialize_sls(session, APP_VERSION)
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


@router.post("/import-sls")
def import_sls(request: Request, file: UploadFile = File(...), session=Depends(get_session_state)):
    """
    Portable Search Sessions (#91) -- the counterpart to /export/sls.
    Also accepts legacy .jis files (#136's backward-compatibility
    requirement) -- parse_sls_import() doesn't care which extension
    the upload had, only the JSON "format" tag inside it.
    Always genuinely RE-RUNS the search against the live database
    (via _execute_search, the exact function a manual search calls)
    rather than replaying the file's results_snapshot -- a session
    opened days later or on another device should reflect the current
    database, not a stale copy of it.
    """
    raw = file.file.read()

    try:
        search = parse_sls_import(raw, MIN_FALLBACK_TAGS)
    except InvalidSlsFile as exc:
        # InvalidSlsFile's message is a fixed, known English string
        # from services/sls_format.py (framework-agnostic, no i18n of
        # its own) -- look it up here rather than teaching that module
        # about locales; unrecognized text (there is none today, but
        # exceptions are still just str(exc)) falls back to itself.
        error_key = "error." + str(exc)
        translated = t(error_key, request.state.locale)
        error_text = str(exc) if translated == error_key else translated
        context = {
            **_filter_context(request.state.locale),
            **_results_context(session),
            "warning": t("warning.sls_load_error", request.state.locale, error=error_text),
        }
        return _render(request, "partials/search_results.html", context, session)

    indexing = search.get("indexing") or []
    if not indexing:
        context = {
            **_filter_context(request.state.locale),
            **_results_context(session),
            "warning": t("warning.sls_no_index", request.state.locale),
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
        **_filter_context(request.state.locale),
        **_results_context(session),
        **_interpreter_form_context(session),
        **language_form_context(session, request.state.locale),
    }
    return _render(request, "partials/search_results.html", context, session)
