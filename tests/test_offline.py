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
import requests
from fastapi.testclient import TestClient

from web.main import app
from web.dependencies import SESSION_COOKIE_NAME
from web.session_store import get_session
from services import dataset_updater, online_enrichment, prefs
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


# ---------------------------------------------------------------------
# Dataset versioning and background updates (#153)
#
# Every test below runs against tmp_path-redirected paths, NEVER the
# real data/journal_intelligence.db or data/.db_version -- accidentally
# pointing apply_update() at the real files would os.replace() over
# the actual committed 55MB database. isolated_paths patches
# dataset_updater's module-level path constants directly (the same
# pattern services/repository.py's own DATA_DIR/DB_PATH already use),
# not the real ones.
# ---------------------------------------------------------------------

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_updater, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dataset_updater, "DB_PATH", tmp_path / "journal_intelligence.db")
    monkeypatch.setattr(dataset_updater, "DB_NEW_PATH", tmp_path / "journal_intelligence.db.new")
    monkeypatch.setattr(dataset_updater, "VERSION_FILE_PATH", tmp_path / ".db_version")
    monkeypatch.setattr(dataset_updater, "_PENDING_VERSION_PATH", tmp_path / ".db_version.pending")
    return tmp_path


class _BytesHandler(BaseHTTPRequestHandler):
    """Serves fixed bytes set as a class attribute -- swapped per test
    via _serve(). Matches tests/test_ai_provider.py's own local-stub-
    server pattern rather than mocking requests directly, so this is a
    real HTTP round trip, not a mocked one."""
    payload = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        pass  # keep test output quiet


def _serve(payload: bytes):
    _BytesHandler.payload = payload
    server = HTTPServer(("127.0.0.1", 0), _BytesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}/journal_intelligence.db"


@pytest.mark.parametrize("local_version,remote_version,expected", [
    ("2026.01.01", "2026.09.02", True),   # remote newer
    ("2026.09.02", "2026.09.02", False),  # same version
    ("2026.09.02", "2026.01.01", False),  # remote older (shouldn't happen server-side, but must not "downgrade")
    ("0000.00.00", "2026.01.01", True),   # no local version on disk yet -- always outdated
    ("2025.12.31", "2026.01.01", True),   # crosses a year boundary -- string comparison alone would still get
                                           # this right by luck (zero-padded), the real reason _parse_version
                                           # compares tuples of ints instead
])
def test_version_comparison(isolated_paths, monkeypatch, local_version, remote_version, expected):
    if local_version != "0000.00.00":
        dataset_updater.VERSION_FILE_PATH.write_text(local_version, encoding="utf-8")
    # isolated_paths' tmp_path has no .db_version file when local_version
    # is the "0000.00.00" sentinel -- get_local_version()'s own
    # documented fallback for that case, not something this test fakes.

    monkeypatch.setattr(
        dataset_updater, "check_remote_version", lambda: {"version": remote_version}
    )

    assert dataset_updater.is_update_available() is expected


def test_update_check_network_failure(isolated_paths, network_blocked):
    """
    VERSION_URL is a real, always-set constant now (GitHub Releases,
    not the old Cloudcube env-var-that-might-be-unset design) -- no
    monkeypatching needed to make check_remote_version() actually
    attempt a connection here; it always does. Also asserts no AWS/
    boto3-shaped error surfaces anywhere in the stack -- there's
    nothing left in this module that could raise one, since it never
    imports boto3 at all (#153 follow-up: Cloudcube removed from this
    path entirely).
    """
    result = dataset_updater.check_remote_version()
    assert result is None


def test_version_url_real_get_no_credentials_needed():
    """
    The one genuinely "real" check Step 4 asks for: an actual GET
    against raw.githubusercontent.com, no network_blocked fixture, no
    mocking, no AWS/GitHub credential of any kind (a public repo's raw
    file needs none). 200 (data/version.json exists on `main`) or 404
    (this exact commit hasn't reached GitHub yet) are both acceptable
    -- what must NOT happen is an exception, a hang, or any sign this
    ever needed a credential.
    """
    response = requests.get(dataset_updater.VERSION_URL, timeout=10)
    assert response.status_code in (200, 404), (
        f"expected 200 or 404 from a public raw.githubusercontent.com URL, got {response.status_code}"
    )

    # check_remote_version() itself must handle whichever of the two
    # this actually was without raising, consistent with that status.
    result = dataset_updater.check_remote_version()
    if response.status_code == 200:
        assert isinstance(result, dict) and result.get("version")
    else:
        assert result is None


def test_sha256_verification(isolated_paths):
    payload = b"not a real sqlite database, just test bytes"
    server, url = _serve(payload)
    try:
        wrong_sha256 = "0" * 64
        result = dataset_updater.download_update(url, wrong_sha256, size_bytes=len(payload))
        assert result is False
        assert not dataset_updater.DB_NEW_PATH.exists(), "a checksum-mismatched download must not be left on disk"
    finally:
        server.shutdown()


def test_download_update_succeeds_with_correct_sha256(isolated_paths):
    payload = b"not a real sqlite database, just test bytes"
    correct_sha256 = hashlib.sha256(payload).hexdigest()
    server, url = _serve(payload)
    try:
        result = dataset_updater.download_update(url, correct_sha256, size_bytes=len(payload))
        assert result is True
        assert dataset_updater.DB_NEW_PATH.read_bytes() == payload
    finally:
        server.shutdown()


def test_apply_update_swaps_file_and_records_version(isolated_paths):
    dataset_updater.DB_PATH.write_bytes(b"old database contents")
    dataset_updater.DB_NEW_PATH.write_bytes(b"new database contents")
    dataset_updater.stage_pending_version("2026.09.02")

    assert dataset_updater.apply_update() is True
    assert dataset_updater.DB_PATH.read_bytes() == b"new database contents"
    assert not dataset_updater.DB_NEW_PATH.exists()
    assert dataset_updater.get_local_version() == "2026.09.02"


def test_apply_update_deferred_while_search_lock_held(isolated_paths):
    """
    The actual mechanism web/routers/search.py's
    _execute_unified_search() relies on: apply_update() must never
    swap the live DB out from under a real search. Acquiring
    dataset_updater.SEARCH_LOCK directly here (the same lock object
    the search path uses) simulates "a search is in progress" without
    needing to orchestrate a real concurrent HTTP request.
    """
    dataset_updater.DB_PATH.write_bytes(b"old database contents")
    dataset_updater.DB_NEW_PATH.write_bytes(b"new database contents")
    dataset_updater.stage_pending_version("2026.09.02")

    dataset_updater.SEARCH_LOCK.acquire()
    try:
        assert dataset_updater.apply_update() is False
        assert dataset_updater.DB_PATH.read_bytes() == b"old database contents", "must not swap while locked"
        assert dataset_updater.DB_NEW_PATH.exists(), "the verified download must survive a deferred apply"
    finally:
        dataset_updater.SEARCH_LOCK.release()

    # Lock free again now -- the retry this simulates would succeed.
    assert dataset_updater.apply_update() is True
    assert dataset_updater.DB_PATH.read_bytes() == b"new database contents"


def test_apply_update_with_retry_gives_up_after_max_attempts(isolated_paths):
    """
    apply_update_with_retry()'s actual retry loop (#153: "retry after
    30 seconds"), with sleep_fn stubbed out so this doesn't really
    wait -- proves the retry/give-up logic itself, not real timing.
    """
    dataset_updater.DB_PATH.write_bytes(b"old database contents")
    dataset_updater.DB_NEW_PATH.write_bytes(b"new database contents")
    dataset_updater.stage_pending_version("2026.09.02")

    sleep_calls = []
    dataset_updater.SEARCH_LOCK.acquire()
    try:
        result = dataset_updater.apply_update_with_retry(
            max_attempts=3, retry_seconds=30, sleep_fn=sleep_calls.append,
        )
    finally:
        dataset_updater.SEARCH_LOCK.release()

    assert result is False
    assert sleep_calls == [30, 30]  # slept between attempts 1->2 and 2->3, not after the last one
    assert dataset_updater.DB_PATH.read_bytes() == b"old database contents", "must still not have swapped"


# ---------------------------------------------------------------------
# Settings panel (#155) -- prefs.json storage and the /settings routes.
#
# isolated_prefs redirects platformdirs.user_config_dir() to tmp_path
# for the duration of each test -- services/prefs.py imports
# platformdirs lazily (inside _prefs_path(), not at module level, so
# that importing services.prefs/web.routers.settings stays safe on a
# machine without requirements-desktop.txt installed), and every call
# below re-resolves the path through that same patched function, so
# nothing here ever touches the real ~/.config/scilene/prefs.json.
# ---------------------------------------------------------------------

import platformdirs


@pytest.fixture
def isolated_prefs(tmp_path, monkeypatch):
    monkeypatch.setattr(platformdirs, "user_config_dir", lambda *a, **kw: str(tmp_path))
    return tmp_path


def test_prefs_defaults(isolated_prefs):
    assert prefs.load_prefs() == {
        "language": "en",
        "dataset_auto_update": True,
        "theme": "light",
    }


def test_prefs_roundtrip(isolated_prefs):
    prefs.set_pref("theme", "dark")
    assert prefs.get_pref("theme") == "dark"

    # The file was actually written, not just cached in memory -- a
    # completely fresh load_prefs() call (no shared state with
    # set_pref() above beyond the file on disk) still sees it.
    reloaded = prefs.load_prefs()
    assert reloaded["theme"] == "dark"
    assert reloaded["language"] == "en"  # untouched defaults survive alongside the one changed key


def test_prefs_corrupt_file(isolated_prefs):
    prefs_path = isolated_prefs / "prefs.json"
    prefs_path.parent.mkdir(parents=True, exist_ok=True)
    prefs_path.write_text("{not valid json", encoding="utf-8")

    assert prefs.load_prefs() == {
        "language": "en",
        "dataset_auto_update": True,
        "theme": "light",
    }


def test_settings_endpoint(client, isolated_prefs):
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Language" in response.text
    assert "Appearance" in response.text


def test_language_setting_ar_blocked_on_web(client, isolated_prefs, monkeypatch):
    monkeypatch.setenv("SCILENE_RUNTIME", "web")
    prefs.set_pref("language", "en")

    response = client.post("/settings/language", data={"language": "ar"})
    assert response.status_code in (400, 303, 307)

    assert prefs.get_pref("language") == "en", "must not have saved 'ar' while blocked"
