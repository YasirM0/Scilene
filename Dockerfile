# Runs the FastAPI web app (web/main.py). Not wired into any specific
# hosting platform on purpose -- no platform was chosen yet, and this
# stays usable on Render, Railway, Fly.io, a plain VPS, or anywhere else
# that runs a container. Rebuild web/static/css/output.css locally with
# `npm run build:css` before building the image; there's no Node stage
# here since the built CSS is committed to the repo already.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -r appuser && chown -R appuser /app
USER appuser

ENV JI_HOST=0.0.0.0
ENV JI_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
