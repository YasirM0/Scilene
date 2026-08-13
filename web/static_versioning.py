"""
Automatic, per-file cache-busting for static assets (#143 follow-up).

A real bug report ("the filter gating doesn't work") turned out to be a
stale browser cache of multiselect.js -- fixed live, but a URL tied to
APP_VERSION alone would only protect FUTURE visitors if a developer
remembers to bump that version every time they touch a static file,
which is exactly the discipline that failed here (multiselect.js was
edited many times this session without a version bump). Deriving the
cache-busting token from each file's own last-modified time instead
means it's automatically correct the moment a file changes, with zero
extra step required, for every browser regardless of its own caching
heuristics -- the URL itself is different, so there's nothing to
misjudge.

Computed once per file path and cached in-memory: these files don't
change while a single server process is running (any code change
needs a process restart anyway, per this app's whole deployment
model -- uvicorn --reload restarts the process, and a production
redeploy always restarts it too), so re-stat'ing on every request
would be pure overhead for no correctness benefit.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"

_cache: dict[str, str] = {}


def static_version(relative_path: str) -> str:
    """
    Cache-busting token for a file under web/static/, derived from its
    mtime. Falls back to "0" if the file can't be stat'd (e.g. a
    typo'd path) -- a wrong-but-stable token is better than a 500 in
    template rendering over what's ultimately just a cosmetic query
    string.
    """
    if relative_path not in _cache:
        try:
            mtime = (STATIC_DIR / relative_path).stat().st_mtime
            _cache[relative_path] = str(int(mtime))
        except OSError:
            _cache[relative_path] = "0"
    return _cache[relative_path]
