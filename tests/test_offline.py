"""
Offline verification suite (#154).

Confirms the app's core paths -- search (English/Indonesian/Arabic),
exports, and the translation layer -- genuinely make zero network
calls, and that the two real network call sites the #154 audit found
(services/ai_provider.py's CloudAIProvider._call, and
services/online_enrichment.py's provider fetches) degrade gracefully
under a hard network block instead of hanging or raising.

Response shape note: /search and /search/export/* are server-rendered
HTML/HTMX endpoints, not a JSON API -- there is no `results` list or
`suggest_desktop` field in the response body. "Results list" here
means the actual data structure the route itself populates:
web/session_store.py's get_session()[...]["visible_results"] (set as
a side effect of web/routers/search.py's _results_context(), which
every rendering route calls). Inspecting that directly is more robust
than scraping HTML and is what "non-empty results" concretely means
in this app. Likewise, the Arabic-blocked case doesn't set a
suggest_desktop flag -- it puts services.query_translator's real
ARABIC_DESKTOP_MESSAGE into the rendered warning, which is what's
asserted below instead.

Export note: there is no per-journal-ID export route -- GET
/search/export/{fmt} exports whatever is currently in the session's
visible_results (web/routers/search.py's export_results()), so the
export tests run a real search first, then export from that same
session.
"""

import socket

import pytest
from fastapi.testclient import TestClient

from web.main import app
from web.dependencies import SESSION_COOKIE_NAME
from web.session_store import get_session
from services import online_enrichment
from services.ai_provider import CloudAIProvider
from services.query_translator import (
    translate_query,
    ArabicNotSupportedOnline,
    ARABIC_DESKTOP_MESSAGE,
    _has_argos_ar_en,
)

STRATEGY_LABEL = "⚖️ Balanced (Recommended)"
ALL_INDEXING = ["DOAJ", "Scopus", "SINTA", "Web of Science"]


def _search_form(abstract):
    return {
        "abstract": abstract,
        "strategy_label": STRATEGY_LABEL,
        "indexing": ALL_INDEXING,
    }


def _session_from(client):
    """
    The real session dict a just-completed request populated --
    web/dependencies.py sets ji_session on the response, and
    web/session_store.py's module-level _SESSIONS dict is the actual
    source of truth the route read/wrote, not anything the response
    body exposes directly.
    """
    session_id = client.cookies.get(SESSION_COOKIE_NAME)
    assert session_id, "no session cookie was set on the response"
    return get_session(session_id)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def network_blocked(monkeypatch):
    """
    Simulates a machine with no internet access. Patches
    socket.socket.connect/connect_ex specifically (not the socket.socket
    constructor itself, and not e.g. just requests.get) so this catches
    ANY library actually attempting an outbound connection, not just
    the ones already known about -- the whole point of an offline
    *verification* suite is catching what the manual audit might have
    missed, not just re-confirming what it already found.

    Patching the constructor instead (socket.socket = ...) was the
    first thing tried here and broke asyncio's own internals: its
    event loop opens a local AF_UNIX socketpair for its self-pipe via
    socket.socketpair() -> socket.socket(...), which has nothing to do
    with real network access and shouldn't be blocked -- doing so took
    TestClient itself down with an unrelated OSError. connect()/
    connect_ex() is the actual moment code reaches out to a remote
    address (what requests/urllib3 call internally), so patching there
    blocks real network access without touching socket construction,
    local socketpairs, bind(), etc.

    Function-scoped: monkeypatch reverts automatically at the end of
    each test, so this can't leak into unrelated tests or into the
    module-level TestClient/app construction that already happened
    before any test ran.

    Safe to combine with TestClient: httpx's ASGI transport calls the
    app in-process (no real socket involved for that traffic at all),
    so this only affects code that tries to make an actual outbound
    connection -- exactly what it's meant to catch.
    """
    def _blocked_connect(self, *args, **kwargs):
        raise OSError("Network blocked by offline test suite")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect)
    yield


# ---------------------------------------------------------------------
# 2. Core search, under network block
# ---------------------------------------------------------------------

def test_search_english_query_offline(client, network_blocked):
    response = client.post(
        "/search",
        data=_search_form("machine learning natural language processing for scientific literature"),
    )
    assert response.status_code == 200

    session = _session_from(client)
    assert session.get("visible_results"), "expected non-empty results for an English query"


def test_search_indonesian_query_offline(client, network_blocked):
    response = client.post(
        "/search",
        data=_search_form("pembelajaran mesin dan kecerdasan buatan"),
    )
    assert response.status_code == 200

    session = _session_from(client)
    assert session.get("visible_results"), "expected non-empty results for an Indonesian query"


@pytest.mark.skipif(
    not _has_argos_ar_en(),
    reason="Argos ar->en package not installed in this interpreter -- "
           "desktop-only (requirements-desktop.txt), not part of the web build.",
)
def test_search_arabic_query_offline_desktop(client, network_blocked, monkeypatch):
    monkeypatch.setenv("SCILENE_RUNTIME", "desktop")

    response = client.post(
        "/search",
        data=_search_form("الصحة العامة والوبائيات"),
    )
    assert response.status_code == 200
    assert ARABIC_DESKTOP_MESSAGE not in response.text, (
        "desktop runtime should translate and search, not show the "
        "web-only Arabic-blocked message"
    )

    session = _session_from(client)
    assert session.get("visible_results"), "expected real journal results for a translated Arabic query"


def test_search_arabic_query_offline_web(client, network_blocked, monkeypatch):
    monkeypatch.setenv("SCILENE_RUNTIME", "web")

    response = client.post(
        "/search",
        data=_search_form("الصحة العامة والوبائيات"),
    )
    assert response.status_code == 200
    assert ARABIC_DESKTOP_MESSAGE in response.text, (
        "web runtime should render the real Arabic-blocked message, "
        "not a generic error"
    )

    session = _session_from(client)
    assert not session.get("visible_results"), "expected no results when Arabic is blocked"


# ---------------------------------------------------------------------
# 3. Exports, under network block
# ---------------------------------------------------------------------

@pytest.fixture
def client_with_results(client, network_blocked):
    """A session with real, non-empty visible_results already in it --
    what every export route actually reads from (see module docstring:
    there's no per-journal-ID export endpoint)."""
    response = client.post(
        "/search",
        data=_search_form("machine learning natural language processing for scientific literature"),
    )
    assert response.status_code == 200
    assert _session_from(client).get("visible_results"), "search must produce results before exports can be tested"
    return client


@pytest.mark.parametrize("fmt,expected_content_type", [
    ("pdf", "application/pdf"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
])
def test_export_offline(client_with_results, fmt, expected_content_type):
    response = client_with_results.get(f"/search/export/{fmt}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(expected_content_type)
    assert len(response.content) > 0


# ---------------------------------------------------------------------
# 4. Graceful degradation of the network-dependent features themselves
# ---------------------------------------------------------------------

def test_research_idea_generate_offline(client, network_blocked):
    """
    POST /research-idea/generate never actually reaches
    CloudAIProvider today (get_default_provider() always returns
    PlaceholderProvider -- see services/ai_provider.py), so this
    mainly guards against that changing silently: whatever provider
    answers, the route must never 500 under a hard network block.
    """
    response = client.post("/research-idea/generate", data={"idea": "a study of coral reef ecosystems"})
    assert response.status_code != 500


def test_cloud_ai_provider_degrades_gracefully_offline(network_blocked):
    """
    Directly exercises services/ai_provider.py:228's requests.post()
    call -- the actual network call site the #154 audit named, which
    the route test above doesn't reach today since PlaceholderProvider
    is the active default. Per AIProvider's contract (CloudAIProvider's
    own docstring), a connection failure must come back as
    AIResponse(ok=False, error=...), never raise or hang.
    """
    provider = CloudAIProvider(endpoint_url="http://127.0.0.1:1")  # nothing ever listens on port 1
    response = provider.suggest_concepts("A study of coral reef ecosystems.")
    assert response.ok is False
    assert response.error


def test_online_enrichment_degrades_gracefully_offline(network_blocked):
    """
    services/online_enrichment.py's own docstring already documents
    this contract (returns None, never raises, on total failure) --
    this proves it holds under an actual hard network block, not just
    against a merely-unreachable-but-real host.
    """
    result = online_enrichment.enrich("1234-5678", None)
    assert result is None


def test_enrich_route_offline(client, network_blocked):
    response = client.post("/search/enrich", data={"issn_print": "1234-5678", "issn_online": ""})
    assert response.status_code != 500


# ---------------------------------------------------------------------
# 5. Translation layer -- pure unit tests, no network fixture
# ---------------------------------------------------------------------

def test_translate_query_english_passthrough():
    # Not "marine biology" alone -- langdetect (statistical, no network
    # involved either way) genuinely misreads that specific short
    # phrase as Italian; verified directly, deterministic given this
    # module's DetectorFactory.seed = 0, not test flakiness. A longer,
    # less ambiguous phrase is what actually exercises the "en passes
    # through unchanged" behavior this test is for.
    text, lang = translate_query("marine biology research methods")
    assert text == "marine biology research methods"
    assert lang == "en"


def test_translate_query_indonesian_dictionary():
    text, lang = translate_query("biologi kelautan")
    assert lang == "id"
    assert "marine" in text.lower() or "biology" in text.lower()


@pytest.mark.skipif(
    not _has_argos_ar_en(),
    reason="Argos ar->en package not installed in this interpreter -- "
           "desktop-only (requirements-desktop.txt), not part of the web build.",
)
def test_translate_query_arabic_desktop(monkeypatch):
    monkeypatch.setenv("SCILENE_RUNTIME", "desktop")
    text, lang = translate_query("الصحة العامة")
    assert lang == "ar"
    assert text.strip()
    assert text.isascii(), f"expected translated English text, got {text!r}"


def test_translate_query_arabic_web_blocked(monkeypatch):
    monkeypatch.setenv("SCILENE_RUNTIME", "web")
    with pytest.raises(ArabicNotSupportedOnline):
        translate_query("الصحة العامة")
