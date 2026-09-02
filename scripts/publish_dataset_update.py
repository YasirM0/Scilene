"""
Publishes a new data/journal_intelligence.db to Cloudcube for the
desktop app's background update checker (#153) to find.

Maintainer-only, never run by the live app itself (see
services/dataset_updater.py, which only ever reads version.json and
downloads db_url -- both plain HTTPS GETs, no AWS credentials).
Reuses scripts/fetch_source_csvs.py's own Cloudcube client/region
setup rather than duplicating that logic -- same shared multi-tenant
bucket, same CLOUDCUBE_* env vars (see that module's docstring for
what those are and how to get them).

Publishes both the DB and version.json with ACL=public-read: the
desktop app has no AWS credentials at all (shipping Cloudcube's
secret key inside every desktop install would leak it to every user),
so both objects must be readable via a plain unauthenticated GET, not
just a boto3-signed one. Cloudcube's shared bucket may or may not
honor object-level ACLs depending on how it's provisioned -- verify
this actually results in a publicly-fetchable URL against your real
Cloudcube instance before relying on it; this hasn't been (and can't
be, from here) verified against a live Cloudcube bucket.

Run from the project root:
    python -m scripts.publish_dataset_update
"""

import hashlib
import json
from datetime import date
from pathlib import Path

from scripts.fetch_source_csvs import _cube_client_and_prefix

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "journal_intelligence.db"
VERSION_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / ".db_version"

DB_OBJECT_NAME = "journal_intelligence.db"
VERSION_OBJECT_NAME = "version.json"


def _sha256_of(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_local_version():
    if VERSION_FILE_PATH.exists():
        return VERSION_FILE_PATH.read_text(encoding="utf-8").strip()
    return date.today().strftime("%Y.%m.%d")


def publish():
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found -- nothing to publish.")

    version = _read_local_version()
    size_bytes = DB_PATH.stat().st_size
    print(f"Computing sha256 of {DB_PATH} ({size_bytes / 1e6:.1f} MB)...", flush=True)
    sha256 = _sha256_of(DB_PATH)

    client, bucket, prefix = _cube_client_and_prefix()

    db_key = f"{prefix}/{DB_OBJECT_NAME}"
    version_key = f"{prefix}/{VERSION_OBJECT_NAME}"
    db_url = f"https://{bucket}.s3.amazonaws.com/{db_key}"

    print(f"Uploading {DB_PATH} -> {db_key} ...", flush=True)
    client.upload_file(str(DB_PATH), bucket, db_key, ExtraArgs={"ACL": "public-read"})

    manifest = {
        "version": version,
        "db_url": db_url,
        "sha256": sha256,
        "size_bytes": size_bytes,
    }
    print(f"Uploading {version_key} ...", flush=True)
    client.put_object(
        Bucket=bucket,
        Key=version_key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
        ACL="public-read",
    )

    print(f"Published version {version} ({size_bytes / 1e6:.1f} MB) to Cloudcube")


if __name__ == "__main__":
    publish()
