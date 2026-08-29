# Architecture Decisions

This document records major architectural decisions made during the development
of Scilene and the reasoning behind them.

---

## 2026-07

### Frontend Migration

Decision:
Migrate from Streamlit to FastAPI + Jinja2 + HTMX + Tailwind CSS.

Reason:

- Streamlit became limiting for a production-quality interface.
- Full-page rerenders reduced responsiveness.
- Fine-grained control over UI was required.
- Future desktop packaging should reuse the backend.
- FastAPI naturally supports future REST APIs.

Alternatives considered:

- NiceGUI
- Reflex
- Gradio
- Django + HTMX
- Flet

Result:

FastAPI provided the best balance between performance, maintainability,
hosting flexibility, and future Tauri compatibility.

## Backend Architecture

Decision:

Keep the recommendation engine completely independent of the frontend.

Reason:

The backend should be reusable by:

- Streamlit
- FastAPI
- Future desktop application
- Future REST API

Implementation:

UI

↓

search_service.py

↓

repository.py

↓

SQLite

## Database

Decision:

SQLite remains the primary database.

Reason:

- Easy local development
- Desktop compatibility
- Single-file distribution
- Can later migrate to PostgreSQL without changing repositories.

## Future Desktop

Decision:

Do not build the desktop application yet.

Reason:

The web application has priority.

The backend architecture is already prepared for Tauri if a desktop version
is developed later.

