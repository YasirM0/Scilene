# Journal Intelligence

> Researchers deserve recommendations they can understand and trust.

**Most journal finders tell you which journals match your paper. Journal Intelligence tells you *why* they match.**

Journal Intelligence is an open-source journal recommendation platform that combines semantic search, transparent ranking, and practical publishing information to help researchers make informed submission decisions.

## Overview

Choosing an appropriate journal is one of the most difficult parts of academic publishing. Existing journal recommendation tools often rely on opaque algorithms, require paid services, or prioritize prestige over researchers' actual goals.

Journal Intelligence aims to provide an open, transparent, and community-driven alternative.

Rather than asking "Which journal is the best?", Journal Intelligence helps answer:

> "Which journal is the best choice for **my research and my publishing goals**?"

---

## Version 0.1 Goals

Version 0.1 focuses on doing one thing exceptionally well:

- Recommend suitable journals based on a paper's title and abstract.
- Explain why each journal is recommended.
- Allow practical filtering such as:
  - Scopus / SINTA
  - APC
  - Quartile
  - Language
- Keep the recommendation process transparent and reproducible.

---

## Core Principles

- 🔍 Transparent recommendations
- 🌍 Open source
- 🧩 Modular architecture
- 🔒 Privacy by default
- 📖 Evidence over assumptions
- 🚀 Simplicity before complexity

---

## Planned Features

### Version 0.1

- Semantic journal search
- Transparent ranking
- Journal filters
- Simple and Advanced search modes
- Export results

### Future Versions

- Full manuscript analysis
- AI-assisted writing suggestions
- Submission planning
- Community statistics
- Optional LLM integration

---

## Technology

The initial implementation is planned using:

- Python
- Streamlit
- SQLite
- FAISS
- Sentence Transformers

The architecture remains modular so components can be replaced without redesigning the project.

---

## Project Status

Journal Intelligence is currently in active development.

Current milestone:

Sprint 1 — Application Skeleton

Version:

v0.1.0-alpha

---

## Running the app

### Streamlit (current, complete)

```
streamlit run app/main.py
```

### Web app (v0.2.0, in progress — Phase 1 only)

FastAPI + Jinja2 + HTMX + Tailwind is being migrated to alongside the
Streamlit app, not replacing it yet. Phase 1 only proves the
architecture — a placeholder homepage that calls the real backend
(`services.repository.count_journals()`) and renders it. No search
functionality has moved here yet.

```
pip install -r requirements.txt
uvicorn web.main:app --reload
```

Then open http://127.0.0.1:8000/.

To rebuild the Tailwind CSS after changing a template's classes:

```
npm install
npm run build:css
```

See docs/WEB_MIGRATION.md for the full architecture rationale.

---

## Documentation

See docs/INDEX.md for the complete documentation.

---

## Contributing

Contributions are welcome.

Before submitting code, please read:

- CONTRIBUTING.md
- ROADMAP.md

---

## License

MIT License