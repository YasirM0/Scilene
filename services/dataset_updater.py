"""
Background dataset version checking and updating for the desktop app
(#153). data/journal_intelligence.db ships bundled with every install
(same convention as the ONNX models); this module is what lets a
later, smaller update replace it without a full reinstall.

Never imported by the web/Heroku build's actual request path -- see
web/main.py's startup wiring, gated on SCILENE_RUNTIME == "desktop".
The web deployment's database gets refreshed by
scripts/publish_dataset_update.py + a manual redeploy instead, exactly
like today.

Client/server contract (scripts/publish_dataset_update.py writes the
server side of this):
    GET {SCILENE_DATASET_VERSION_URL}
    -> {"version": "YYYY.MM.DD", "db_url": "https://...",
        "sha256": "...", "size_bytes": 12345}
Both requests are plain, unauthenticated HTTPS GETs -- the desktop app
never holds any Cloudcube/AWS credential, only the maintainer-run
publish script does.

Thread safety: SEARCH_LOCK is the actual lock a real search acquires
for its duration (see web/routers/search.py's _execute_unified_search)
-- apply_update() only ever tries a non-blocking acquire, so it can
never make a search wait, only defer the swap itself to the next
retry.
"""

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "journal_intelligence.db"
DB_NEW_PATH = DATA_DIR / "journal_intelligence.db.new"
VERSION_FILE_PATH = DATA_DIR / ".db_version"
# Where download_update() stashes the version it just downloaded, so
# apply_update() (which takes no arguments, per #153's own design)
# knows what to write to VERSION_FILE_PATH after the swap -- without
# this, that information would only ever have existed in the
# background thread's local variables between the two calls.
_PENDING_VERSION_PATH = DATA_DIR / ".db_version.pending"

# A real, hard-coded default would either be some maintainer's actual
# infrastructure (wrong to bake into source) or a placeholder that
# silently "works" until someone hits it in production -- unset means
# every check_remote_version() call below returns None immediately,
# which is exactly the same safe "no update available" behavior as a
# real but unreachable URL, just without a wasted network attempt.
VERSION_JSON_URL_ENV_VAR = "SCILENE_DATASET_VERSION_URL"

VERSION_CHECK_TIMEOUT_SECONDS = 3
DOWNLOAD_TIMEOUT_SECONDS = (5, 300)  # (connect, read) -- a 55MB+ file legitimately takes longer than 3s
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

APPLY_RETRY_SECONDS = 30
APPLY_MAX_ATTEMPTS = 10  # ~5 minutes of retrying before giving up for this launch

# Acquired for the duration of an actual search (web/routers/search.py)
# -- apply_update() only ever does a non-blocking acquire against this,
# never blocks a search waiting for it.
SEARCH_LOCK = threading.Lock()


def get_local_version() -> str:
    """
    The version currently on disk. "0000.00.00" (sorts before every
    real date-shaped version) if data/.db_version doesn't exist yet --
    that's a real, if unlikely, state (a build that shipped without
    running Step 1's setup), and treating it as "definitely outdated"
    is the safe direction to fail in, not "definitely current".
    """
    if VERSION_FILE_PATH.exists():
        version = VERSION_FILE_PATH.read_text(encoding="utf-8").strip()
        if version:
            return version
    return "0000.00.00"


def _version_json_url():
    return os.environ.get(VERSION_JSON_URL_ENV_VAR)


def check_remote_version() -> dict | None:
    """
    Returns version.json's parsed contents, or None on ANY failure --
    unset URL, unreachable host, timeout, non-200, malformed JSON.
    Every one of those means the same thing to a caller: no usable
    remote version info right now, proceed with the local DB. Never
    raises.
    """
    url = _version_json_url()
    if not url:
        return None

    try:
        response = requests.get(url, timeout=VERSION_CHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except Exception:
        logger.info("Dataset version check failed or unreachable -- using local DB", exc_info=True)
        return None


def _parse_version(version: str):
    """
    "YYYY.MM.DD" -> (YYYY, MM, DD) for a real tuple comparison --
    string comparison alone happens to work for this exact
    zero-padded format too, but only by accident (breaks the moment
    any part isn't zero-padded), so this doesn't lean on that.
    Anything that doesn't parse sorts as the oldest possible version,
    the same safe-direction failure as get_local_version()'s own
    default.
    """
    try:
        parts = tuple(int(p) for p in version.strip().split("."))
        if len(parts) != 3:
            raise ValueError(f"expected 3 dot-separated parts, got {version!r}")
        return parts
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_update_available() -> bool:
    remote = check_remote_version()
    if not remote or not remote.get("version"):
        return False

    return _parse_version(remote["version"]) > _parse_version(get_local_version())


def download_update(db_url: str, expected_sha256: str, size_bytes: int | None = None) -> bool:
    """
    Downloads db_url to DB_NEW_PATH and verifies its sha256 against
    expected_sha256. Meant to run in a daemon thread (see
    web/main.py's startup wiring) -- never touches DB_PATH itself,
    only the live DB's connection code (services/repository.py) does
    that, so a search running concurrently with this is unaffected.

    Returns False (and leaves no .new file behind either way -- a
    half-downloaded or checksum-mismatched file is worse than none,
    since a later run might otherwise skip re-downloading it) for any
    failure: network error, checksum mismatch, or a size_bytes
    mismatch when that was provided.
    """
    try:
        response = requests.get(db_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()

        hasher = hashlib.sha256()
        downloaded = 0
        with open(DB_NEW_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                f.write(chunk)
                hasher.update(chunk)
                downloaded += len(chunk)
    except Exception:
        logger.exception("Dataset download failed")
        _discard_partial_download()
        return False

    if size_bytes is not None and downloaded != size_bytes:
        logger.error(
            "Dataset download size mismatch: expected %d bytes, got %d", size_bytes, downloaded
        )
        _discard_partial_download()
        return False

    actual_sha256 = hasher.hexdigest()
    if actual_sha256 != expected_sha256:
        logger.error(
            "Dataset checksum mismatch: expected %s, got %s -- discarding download",
            expected_sha256, actual_sha256,
        )
        _discard_partial_download()
        return False

    return True


def _discard_partial_download():
    if DB_NEW_PATH.exists():
        DB_NEW_PATH.unlink()


def stage_pending_version(version: str):
    """
    Records which version download_update() just verified, for
    apply_update() to pick up -- call this after a successful
    download_update(), before apply_update(). Separate from
    download_update() itself since download_update()'s signature and
    return value are exactly what #153 specifies; this is just where
    that information has to live in the meantime.
    """
    _PENDING_VERSION_PATH.write_text(version, encoding="utf-8")


def apply_update() -> bool:
    """
    Swaps DB_NEW_PATH over DB_PATH via os.replace() (atomic on POSIX;
    on Windows a destination file that's genuinely open elsewhere can
    make this raise -- the non-blocking SEARCH_LOCK check below is
    what actually prevents that overlap, on every platform, not
    os.replace()'s own atomicity guarantee alone).

    Returns False without making any change if: there's no verified
    .new file to apply, or a search currently holds SEARCH_LOCK (the
    caller is expected to retry -- see apply_update_with_retry()).
    """
    if not DB_NEW_PATH.exists():
        return False

    acquired = SEARCH_LOCK.acquire(blocking=False)
    if not acquired:
        logger.info("Dataset update deferred -- a search is in progress")
        return False

    try:
        version = _PENDING_VERSION_PATH.read_text(encoding="utf-8").strip() if _PENDING_VERSION_PATH.exists() else None
        os.replace(DB_NEW_PATH, DB_PATH)
        if version:
            VERSION_FILE_PATH.write_text(version, encoding="utf-8")
            if _PENDING_VERSION_PATH.exists():
                _PENDING_VERSION_PATH.unlink()
            logger.info("Dataset updated to version %s", version)
        else:
            logger.info("Dataset file replaced (no pending version recorded)")
        return True
    finally:
        SEARCH_LOCK.release()


def apply_update_with_retry(
    max_attempts: int = APPLY_MAX_ATTEMPTS,
    retry_seconds: float = APPLY_RETRY_SECONDS,
    sleep_fn=time.sleep,
) -> bool:
    """
    apply_update(), retried every retry_seconds while a search holds
    SEARCH_LOCK, up to max_attempts -- what web/main.py's startup
    thread actually calls, matching #153's "if apply is deferred...
    retry after 30 seconds". sleep_fn is overridable purely so tests
    can verify the retry logic without a real 30-second wait.
    """
    for attempt in range(1, max_attempts + 1):
        if apply_update():
            return True
        if not DB_NEW_PATH.exists():
            return False  # nothing to retry -- there was never a verified download to apply
        if attempt < max_attempts:
            sleep_fn(retry_seconds)

    logger.warning("Dataset update still pending after %d attempts -- giving up for this launch", max_attempts)
    return False
