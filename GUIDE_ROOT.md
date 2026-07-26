# GUIDE_ROOT

## Part 1 -- Conceptual Explanation

### Purpose

The project root coordinates a retrieval-focused news search tool. It ties
together:

- the `src/news/` product package,
- the static browser frontend,
- project-wide configuration,
- local verification,
- API exploration notebooks,
- and the user/documentation surface.

The system is intentionally narrow. It searches upstream providers, normalizes
their results, applies local filtering and deduplication, and returns articles
for browsing or export. It does not compute page-level analytics.

### Main workflows from root

1. Start the web app with `uv run news-server`.
2. Open `http://127.0.0.1:8000/` to use the browser UI.
3. Or run the CLI with `uv run news-search "inflation" -s 2025-01-01 -e 2025-03-01`.
4. The API or CLI validates the request before any provider fan-out happens.
5. Requested sources are queried concurrently, with retries for transient
   network or server failures.
6. The merged provider page is post-filtered, optionally deduplicated, sorted,
   and cached for a short in-memory window.
7. The browser renders the current provider page and source-status reports.
8. The CLI can print a table, emit JSON, or export CSV, JSON, or SQLite.

### Root-level inputs and outputs

- Inputs:
  - `.env` credentials for MediaCloud, ACLED, NYT, Guardian, and NewsAPI,
    created locally from the secret-free `.env.example` template.
  - `config.toml` frontend defaults plus cache settings.
  - Browser query parameters or CLI flags.
- Outputs:
  - JSON API responses from `/api/search`, `/api/export/csv`, and `/api/export/json`.
  - Browser-rendered result cards, source-status chips, pagination, and article dialogs.
  - CLI table output and export files under `outputs/` when requested.
  - Local lint and unittest output.

## Part 2 -- Root Tree and File Map

```text
.
├── .env                 -- Local provider credentials.
├── .env.example         -- Secret-free provider credential template.
├── .gitignore           -- Ignore rules for secrets, caches, worktrees, and virtualenv files.
├── .python-version      -- Python version pin for the workspace.
├── README.md            -- Concise entry point with quick start and doc links.
├── config.toml          -- Frontend defaults plus in-memory cache settings.
├── pyproject.toml       -- Project metadata, dependencies, package config, and scripts.
├── uv.lock              -- Locked dependency resolution for `uv`.
├── GUIDE_ROOT.md        -- Root navigation guide.
├── GUIDE_OVERVIEW.md    -- High-level conceptual overview.
├── src/                 -- Importable Python product package.
├── frontend/            -- HTML shell, CSS theme, and JavaScript modules.
├── scripts/             -- Thin one-off helper scripts.
├── tests/               -- Unit tests and route smoke tests.
├── data/                -- Raw, interim, and processed datasets.
├── outputs/             -- CLI exports, reports, figures, and run artifacts.
├── notebooks/           -- Exploration notebooks.
├── docs/                -- User and developer documentation.
└── logs/                -- Runtime log files.
```

See `docs/reference/PROJECT_STRUCTURE.md` for the full file tree.

## Subfolder Overview

- `src/news/`
  - What it does: implements the API, CLI, search pipeline, source adapters, export helpers, and runtime path/config helpers.
  - Key folders: `api/`, `cli/`, `exports/`, `search/`, `sources/`, `web/`.
  - Where outputs go: JSON responses returned to the browser or CLI; export files are written only when requested by the CLI.
  - Guides: `src/GUIDE_src.md`, `src/news/GUIDE_news.md`.

- `frontend/`
  - What it does: renders the browser search experience.
  - Key files: `index.html`, `styles.css`, `scripts/app.js`, `scripts/form.js`, `scripts/render.js`.
  - Where outputs go: no persisted artifacts; output is in-browser.
  - Guide: `frontend/GUIDE_frontend.md`.

- `scripts/`
  - What it does: hosts thin helpers that are not part of the importable product package.
  - Key files: `acled_oauth_token.py`, `acled_bearer_read.py`.
  - Where outputs go: notebook exploration artifacts under `notebooks/api_explorer/*/outputs/`.

- `tests/`
  - What it does: regression coverage for validation, deduplication, export, cache, retry logic, CLI behavior, and route wiring.
  - Key files: `test_search_service.py`, `test_app.py`, `test_cli.py`, `test_export.py`, `test_cache.py`, `test_retry.py`.
  - Where outputs go: none.
  - Guide: `tests/GUIDE_tests.md`.

- `docs/user/`
  - What it does: stores user-facing documentation such as the API reference.
  - Key files: `API_REFERENCE.md`.

- `notebooks/api_explorer/`
  - What it does: notebook-first provider reconnaissance workspace.
  - Key files: source-specific notebooks plus `API_USAGE.md` references.
  - Where outputs go: source-specific `outputs/` folders inside each provider subfolder.
  - Guide: `notebooks/api_explorer/GUIDE_api_explorer.md`.

## Part 3 -- Code Reference

- `pyproject.toml`
  - Defines dependencies, the `src` package layout, and the `news-server` and `news-search` commands.

- `config.toml`
  - Stores frontend defaults and cache settings.
  - Current defaults enable English-only by default and preselect Guardian + NYT.

- `src/news/api/`
  - Owns the FastAPI app, route models, and HTTP query parameter parsing.

- `src/news/search/`
  - Owns validation, shared boundary parsing, cache use, filtering, deduplication, sorting, and response metadata.

- `src/news/sources/`
  - Owns provider registry, concurrent fan-out, retry behavior, shared adapter plumbing, and provider-specific adapters.

- `src/news/exports/`
  - Owns CSV, JSON, and SQLite serialization helpers.

- `src/news/cli/`
  - Owns parser, fetch paths, terminal rendering, export writing, and command workflow.

- `src/news/web/`
  - Owns project-root path resolution and config loading.

- `frontend/`
  - See `frontend/GUIDE_frontend.md` for the browser UI, URL-state handling, pagination, and dialog behavior.

- `tests/`
  - See `tests/GUIDE_tests.md` for the local verification strategy.

- `docs/user/`
  - Holds the current API reference markdown snapshot.
