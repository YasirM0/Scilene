"""
Publishes a new data/journal_intelligence.db as a GitHub Release for
the desktop app's background update checker (#153) to find.
data/version.json is committed to the repo itself and is what
services/dataset_updater.py's VERSION_URL actually fetches (via
raw.githubusercontent.com) -- the DB itself is too large for that, so
it goes to a GitHub Release instead, downloaded from db_url.

Cloudcube (scripts/fetch_source_csvs.py) is unrelated to this --
it stays for its original, only role: rebuilding the DB from source
CSVs. Nothing here imports boto3 or touches Cloudcube; the desktop app
never holds any cloud credential of any kind.

Requires: gh CLI authenticated (gh auth login)
Run from repo root on the maintainer machine only
Never run automatically or in CI

Run from the project root:
    python -m scripts.publish_dataset_update
"""

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

from services.app_info import APP_GITHUB

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "journal_intelligence.db"
VERSION_JSON_PATH = ROOT / "data" / "version.json"
LOCAL_VERSION_PATH = ROOT / "data" / ".db_version"

DB_ASSET_NAME = "journal_intelligence.db"

# APP_GITHUB is "https://github.com/<owner>/<repo>" -- reused rather
# than a second hardcoded literal, so a future rename only ever needs
# fixing in services/app_info.py, the single source of truth for
# project identity.
_OWNER_REPO = APP_GITHUB.rstrip("/").removeprefix("https://github.com/")


def _sha256_of(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _next_version():
    """
    Today's date as the new version -- matches how data/.db_version
    was originally seeded (#153) and how VERSION comparisons work
    (services/dataset_updater.py's _parse_version(), YYYY.MM.DD as a
    real tuple). If a publish already happened today, bumping the day
    again would collide with an existing release tag -- gh release
    create below fails loudly on that rather than silently overwriting
    a previous publish, which is the right failure mode for a
    maintainer-only, manually-run script.
    """
    return date.today().strftime("%Y.%m.%d")


def _run(cmd, **kwargs):
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)


def publish():
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found -- nothing to publish.")

    version = _next_version()
    size_bytes = DB_PATH.stat().st_size
    print(f"Computing sha256 of {DB_PATH} ({size_bytes / 1e6:.1f} MB)...", flush=True)
    sha256 = _sha256_of(DB_PATH)

    db_url = f"https://github.com/{_OWNER_REPO}/releases/download/dataset-{version}/{DB_ASSET_NAME}"

    manifest = {
        "version": version,
        "db_url": db_url,
        "sha256": sha256,
        "size_bytes": size_bytes,
    }
    VERSION_JSON_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    LOCAL_VERSION_PATH.write_text(version + "\n", encoding="utf-8")
    print(f"Updated {VERSION_JSON_PATH}", flush=True)

    _run(["git", "add", str(VERSION_JSON_PATH.relative_to(ROOT)), str(LOCAL_VERSION_PATH.relative_to(ROOT))])
    _run(["git", "commit", "-m", f"chore: publish dataset version {version}"])
    _run(["git", "push"])

    _run([
        "gh", "release", "create", f"dataset-{version}",
        "--title", f"Dataset {version}",
        "--notes", f"Journal index update: {version}",
        str(DB_PATH),
    ])

    print(f"Published dataset version {version} to GitHub Releases")


if __name__ == "__main__":
    publish()
