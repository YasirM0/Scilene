"""
Persistent, per-install desktop settings (#155) -- language, dataset
auto-update, and theme, surviving across launches and across sessions
(web/session_store.py's _SESSIONS dict is per-process and 4-hour TTL;
a browser's localStorage, used today for the nav bar's quick theme
toggle, is per-browser-profile, not guaranteed to survive a Tauri
webview data reset). Desktop-only in spirit -- platformdirs isn't in
requirements.txt (only requirements-desktop.txt), so nothing on the
web/Heroku build ever needs this file to exist.

platformdirs is imported lazily, inside _prefs_path(), not at module
level: web/routers/settings.py is imported unconditionally by
web/main.py (same as every other router), so importing THIS module
must stay safe on a machine that never installed
requirements-desktop.txt -- only calling one of the functions below
would need platformdirs to actually be present.

Not thread-locked: prefs.json is small, read-then-written wholesale
(never partially), and in practice only ever written from the
settings routes (request-handling thread) or the startup update-check
thread, never both at once for the same key in a way that matters --
a lost update to a rarely-changed settings file is an acceptable
tradeoff against the complexity of a lock nothing here has needed yet.
"""

import json
import logging

logger = logging.getLogger(__name__)

APP_NAME = "scilene"
PREFS_FILENAME = "prefs.json"

DEFAULT_PREFS = {
    "language": "en",
    "dataset_auto_update": True,
    "theme": "light",
}


def _prefs_path():
    import platformdirs

    config_dir = platformdirs.user_config_dir(APP_NAME, appauthor=False)
    from pathlib import Path

    return Path(config_dir) / PREFS_FILENAME


def load_prefs() -> dict:
    """
    Always returns a complete dict (every DEFAULT_PREFS key present) --
    missing file, corrupt JSON, or a file missing some keys (an older
    version of this app wrote it before a new pref was added) all fall
    back to defaults for whatever's missing, merged over what's valid.
    Never raises.
    """
    path = _prefs_path()

    if not path.exists():
        return dict(DEFAULT_PREFS)

    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(stored, dict):
            raise ValueError(f"expected a JSON object, got {type(stored).__name__}")
    except Exception:
        logger.warning("Prefs file at %s is missing or corrupt -- using defaults", path, exc_info=True)
        return dict(DEFAULT_PREFS)

    return {**DEFAULT_PREFS, **stored}


def save_prefs(prefs: dict) -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def get_pref(key: str, default=None):
    return load_prefs().get(key, default)


def set_pref(key: str, value) -> None:
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)
