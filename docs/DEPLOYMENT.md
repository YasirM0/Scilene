# Deployment

## Continuous Integration

`.github/workflows/ci.yml` runs on every push and pull request to
`main`. It checks what actually exists in the project today rather
than a full test suite (there isn't one yet — see `tests/README.md`):

1. Installs `requirements.txt`.
2. Imports the FastAPI app (`from web.main import app`) — catches
   broken routes, missing dependencies, or import-time errors before
   they reach a deploy.
3. Runs the recommender smoke test (`python -m tests.test_recommender`)
   against the real committed database (`data/journal_intelligence.db`)
   — catches a broken recommendation path.
4. Builds the Docker image — catches a broken `Dockerfile` or
   `requirements.txt` before it would fail on a real host.

None of these steps deploy anywhere; they only confirm the app is in
a state that *could* be deployed. No hosting platform has been chosen
yet (see the note in `Dockerfile`), so there is no automated deploy
step here — deploying is a manual, deliberate action using one of the
two paths below.

---

## Option 1: Docker

The `Dockerfile` at the repo root runs `web/main.py` and works on any
container host (Render, Railway, Fly.io, a plain VPS, etc.) — it
isn't tied to a specific platform.

```bash
docker build -t scilene .
docker run -p 8000:8000 scilene
```

Rebuild `web/static/css/output.css` locally with `npm run build:css`
before building the image — there's no Node build stage in the
image, the built CSS is committed to the repo already (see
`docs/DESIGN_SYSTEM.md` for why).

---

## Option 2: Heroku

The `Procfile` at the repo root is already set up for Heroku's
standard Python buildpack:

```bash
heroku create
git push heroku main
```

Heroku sets `$PORT` automatically; the `Procfile` passes it straight
to uvicorn.

---

## Environment Variables

All web app settings use the `JI_` prefix (`web/config.py`), read
from the environment or a local `.env` file (see `env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `JI_DEBUG` | `false` | FastAPI debug mode. |
| `JI_HOST` | `0.0.0.0` | Bind host. |
| `JI_PORT` | `8000` | Bind port (Heroku overrides this via `$PORT`). |

No secrets or API keys are required — the app has no external
dependencies at runtime (see "Offline First" in `docs/ARCHITECTURE.md`).

---

**Document Version:** 0.1

**Last Updated:** August 2026

**Status:** Approved
