# Scilene

> Navigate Scholarly Publishing with Confidence

**Scilene** is an open-source journal discovery platform that helps researchers find suitable academic journals through transparent, explainable recommendations powered by authoritative scholarly metadata.

The name combines *Sci* (science) with *Selene*, the Greek personification of the moon — chosen because the moon has long served as a natural guide for navigation and exploration, the same role Scilene aims to play for researchers navigating scholarly publishing. See the in-app About page, or [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md), for the full story behind the name and logo.

Unlike many journal finders that provide only a ranked list, Scilene explains **why** each journal matches your manuscript.

**Live demo:** [scilene-25055279a542.herokuapp.com](https://scilene-25055279a542.herokuapp.com/)

---

## Overview

Choosing an appropriate journal is one of the most challenging parts of academic publishing. Existing recommendation tools often rely on opaque algorithms, paid services, or prestige-based rankings without explaining their decisions.

Scilene provides a transparent, privacy-first alternative built around authoritative datasets and reproducible recommendations.

Rather than asking:

> *"Which journal is the best?"*

Scilene helps answer:

> *"Which journal is the best choice for my research and publishing goals?"*

---

## Core Principles

- 🔍 Transparent recommendations
- 📖 Explainable ranking
- 🔒 Privacy by default
- 🌍 Open source
- 🧩 Modular architecture
- 🚀 Offline-first design
- 📚 Authoritative scholarly metadata

---

## Current Features

- Journal recommendation based on manuscript title and abstract
- Plain-language explanations for every recommendation
- Filtering by:
  - Scopus
  - Web of Science
  - DOAJ
  - SINTA
  - APC
  - Quartile
  - Language
- PDF, DOCX, XLSX, Markdown, CSV, and AI-ready exports
- Fast local search using a SQLite database

---

## Technology

Scilene is built with:

- Python
- FastAPI
- Jinja2
- HTMX
- Tailwind CSS
- SQLite

The application is designed with a modular architecture so that future interfaces (desktop, API, or mobile companion) can reuse the same core recommendation engine.

---

## Project Status

Scilene is under active development.

Current version:

**v0.2.x**

---

## Running the application

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the development server:

```bash
uvicorn web.main:app --reload
```

Then open:

```
http://127.0.0.1:8000
```

To rebuild the Tailwind CSS after modifying templates:

```bash
npm install
npm run build:css
```

---

## Documentation

Project documentation is available in:

```
docs/INDEX.md
```

---

## Related Projects

**[Loupe](https://github.com/YasirM0/loupe)** — a free, open-source citation verifier: checks whether a paper's claims are actually supported by its cited sources, flags uncited claims, and hunts for contradictions between a paper and its references. Runs entirely in-browser, no server or account required. If Scilene helps you find where to publish, Loupe helps you check your citations hold up before you do.

---

## Contributing

Contributions are welcome.

Before contributing, please read:

- CONTRIBUTING.md
- ROADMAP.md

---

## License

MIT License