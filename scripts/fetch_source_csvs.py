"""
Pulls the 3 complete source CSVs -- doaj_complete.csv, scimago_complete.csv,
sinta_complete.csv, each already containing journal metadata plus
scope/index_terms enrichment columns -- from Cloudcube (Heroku's
S3-compatible file storage add-on) into data/processed/.

NOT part of the live app -- web/ and services/ never import this, and
it never runs at request time, on dyno boot, or automatically on
deploy. Purely a manual, on-demand maintenance step: run it locally,
or inside a one-off Heroku dyno right before a database rebuild
(`heroku run python -m scripts.fetch_source_csvs`). The live app
already works on every normal deploy without this -- it only ever
reads data/journal_intelligence.db, which stays committed to git and
ships with every deploy regardless. This script exists solely for when
you deliberately want to refresh that database from newer source data.

These CSVs are kept out of git entirely (data/processed/ is
.gitignore'd) -- doaj_complete.csv alone exceeds GitHub's 100MB
file-size push limit, and the live app never reads data/processed/ in
the first place.

Requires three Heroku config vars, all injected automatically once the
Cloudcube add-on is provisioned (`heroku addons:create cloudcube:free`)
-- never hardcoded or committed here, only ever read from the
environment at runtime:
    CLOUDCUBE_URL                e.g. https://<bucket>.s3.amazonaws.com/<prefix>/
    CLOUDCUBE_ACCESS_KEY_ID
    CLOUDCUBE_SECRET_ACCESS_KEY
Without them, this script -- and by extension scripts/build_database.py
on a fresh clone -- refuses to run. That's intentional: this repo isn't
meant to build a working database without deliberately restoring these
files first.

Run from the project root:
    python -m scripts.fetch_source_csvs            # download
    python -m scripts.fetch_source_csvs --upload    # upload (one-time setup)
"""

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3

DEST_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

FILENAMES = ["doaj_complete.csv", "scimago_complete.csv", "sinta_complete.csv"]

REQUIRED_ENV_VARS = ("CLOUDCUBE_URL", "CLOUDCUBE_ACCESS_KEY_ID", "CLOUDCUBE_SECRET_ACCESS_KEY")


def _cube_client_and_prefix():
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise SystemExit(
            "Missing Cloudcube config var(s): " + ", ".join(missing) + "\n"
            "Provision the add-on first (`heroku addons:create cloudcube:free`), "
            "then export these locally, or they're already set automatically on "
            "Heroku for `heroku run`."
        )

    # CLOUDCUBE_URL looks like https://<bucket>.s3.amazonaws.com/<prefix>/ --
    # a Cloudcube "cube" is just a key prefix inside a bucket SHARED across
    # every Cloudcube customer, so every read/write must stay under that
    # prefix; the bucket name itself is the URL's subdomain.
    parsed = urlparse(os.environ["CLOUDCUBE_URL"])
    bucket = parsed.hostname.split(".")[0]
    prefix = parsed.path.strip("/")

    access_key = os.environ["CLOUDCUBE_ACCESS_KEY_ID"]
    secret_key = os.environ["CLOUDCUBE_SECRET_ACCESS_KEY"]

    # Cloudcube provisions its shared buckets in different regional
    # pools depending on the Heroku app's own region (e.g. a
    # "cloud-cube-eu2"-style bucket lives in an EU region, not
    # us-east-1) -- guessing wrong makes boto3 fail to sign requests
    # correctly, so ask S3 directly rather than hardcoding one.
    probe = boto3.client("s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name="us-east-1")
    region = probe.get_bucket_location(Bucket=bucket)["LocationConstraint"] or "us-east-1"

    client = boto3.client("s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
    return client, bucket, prefix


def fetch_all():
    client, bucket, prefix = _cube_client_and_prefix()
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for filename in FILENAMES:
        dest_path = DEST_DIR / filename
        object_key = f"{prefix}/{filename}"
        print(f"Fetching {object_key} -> {dest_path} ...", flush=True)
        client.download_file(bucket, object_key, str(dest_path))
        print(f"  -> {dest_path} ({dest_path.stat().st_size / 1e6:.1f} MB)", flush=True)

    print(f"\nAll {len(FILENAMES)} files restored -- run scripts/build_database.py next.")


def upload_all():
    """One-time setup: pushes the 3 files from data/processed/ up to
    the cube. Run this once after provisioning Cloudcube, from a
    machine that still has these files locally."""
    client, bucket, prefix = _cube_client_and_prefix()

    for filename in FILENAMES:
        local_path = DEST_DIR / filename
        if not local_path.exists():
            print(f"  SKIP {local_path} (not found locally)", flush=True)
            continue
        object_key = f"{prefix}/{filename}"
        print(f"Uploading {local_path} -> {object_key} ...", flush=True)
        client.upload_file(str(local_path), bucket, object_key)

    print("\nUpload done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true", help="upload local files to the cube instead of downloading")
    args = parser.parse_args()

    upload_all() if args.upload else fetch_all()
