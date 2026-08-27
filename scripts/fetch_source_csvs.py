"""
Pulls the source CSVs no longer committed to this repo -- both the
enriched exports scripts/build_database.py actually reads (sinta_complete
.csv, scimago_complete.csv, doaj_complete.csv, each with appended
scope/index_terms columns, into data/processed/) and their original
data/raw/ counterparts (doaj.csv, scimagojr.csv, sinta.csv), kept purely
as an unenriched provenance backup that build_database.py never
touches -- from a private Hugging Face dataset repo.

NOT part of the live app -- web/ and services/ never import this, and
it never runs at request time or on dyno boot. Purely a manual,
on-demand maintenance step: run it locally, or inside a one-off Heroku
dyno right before a database rebuild (`heroku run python -m
scripts.fetch_source_csvs`), never as part of a regular deploy or web
dyno. These CSVs are kept out of git entirely (data/raw/ and
data/processed/ are both .gitignore'd) -- doaj_complete.csv alone
exceeds GitHub's 100MB file-size push limit, and the live app never
reads either directory in the first place, only
data/journal_intelligence.db (already committed) powers it. wos.csv
is the one exception -- it stays committed under data/enrichment/
since it's small (see scripts/build_database.py's docstring for why
it lives there instead of data/raw/).

Requires HF_TOKEN (a Hugging Face access token with read access to the
private repo below) set as an environment variable -- locally via your
shell/`.env`, or as a Heroku config var (`heroku config:set HF_TOKEN=...`)
if run via `heroku run`. Without it, this script -- and by extension
scripts/build_database.py on a fresh clone -- refuses to run. That's
intentional: this repo isn't meant to build a working database without
deliberately restoring these files first.

Run from the project root:
    python -m scripts.fetch_source_csvs
"""

import os
from pathlib import Path

from huggingface_hub import hf_hub_download

HF_REPO = "YasirM0/scilene-index"
ROOT = Path(__file__).resolve().parent.parent
HF_TOKEN = os.environ.get("HF_TOKEN")

# key -> (filename in the HF repo, destination directory)
FILES = {
    "doaj_raw": ("doaj.csv", ROOT / "data" / "raw"),
    "scimago_raw": ("scimagojr.csv", ROOT / "data" / "raw"),
    "sinta_raw": ("sinta.csv", ROOT / "data" / "raw"),
    "sinta_complete": ("sinta_complete.csv", ROOT / "data" / "processed"),
    "scimago_complete": ("scimago_complete.csv", ROOT / "data" / "processed"),
    "doaj_complete": ("doaj_complete.csv", ROOT / "data" / "processed"),
}


def fetch_all():
    if not HF_TOKEN:
        raise SystemExit(
            "HF_TOKEN is not set -- export it locally, or `heroku config:set "
            "HF_TOKEN=...` before running this via `heroku run`."
        )

    for key, (filename, dest_dir) in FILES.items():
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"Fetching {filename} -> {dest_dir}/ ...", flush=True)
        path = hf_hub_download(
            repo_id=HF_REPO,
            filename=filename,
            repo_type="dataset",
            token=HF_TOKEN,
            local_dir=str(dest_dir),
        )
        print(f"  -> {path} ({Path(path).stat().st_size / 1e6:.1f} MB)", flush=True)

    print(f"\nAll {len(FILES)} files restored -- run scripts/build_database.py next.")


if __name__ == "__main__":
    fetch_all()
