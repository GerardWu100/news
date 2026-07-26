# GUIDE_ROOT

## Part 1 -- Conceptual Explanation

### Purpose

The project root coordinates a historical multi-source news search product. It
connects the importable `src/news/` package, a static browser client, project
configuration, credential bootstrap, tests, and documentation.

The system retrieves provider records, normalizes them into one article model,
applies local filters and optional deduplication, and exposes the results
through a web application and a command-line interface (CLI). It does not crawl
article bodies or provide a general data-science workspace.

### Runtime flow

1. `news-server` starts the FastAPI application and serves the browser client.
2. The browser or CLI turns raw search inputs into a validated request.
3. The search service checks its short-lived in-memory cache.
4. Requested providers run concurrently and return normalized articles plus
   source-specific status.
5. Shared filtering, conservative deduplication, and stable sorting produce the
   response page.
6. The application returns JavaScript Object Notation (JSON), while the CLI can
   also write comma-separated values (CSV), JSON, or SQLite.

### Local state

- `.env` contains provider credentials and is never tracked.
- `config.toml` contains documented frontend and cache settings.
- Exports are created only when a caller requests them; no empty output tree is
  tracked.
- `.venv`, caches, logs, and generated artifacts are ignored.

## Part 2 -- Root Tree and File Map

```text
.
├── README.md
├── config.toml
├── pyproject.toml
├── uv.lock
├── GUIDE_ROOT.md
├── GUIDE_OVERVIEW.md
├── src/                 -- Importable Python product package.
├── frontend/            -- Current static browser client.
├── scripts/             -- Credential bootstrap command.
├── tests/               -- Offline regression and contract tests.
└── docs/
    ├── plans/           -- Current, forward-looking implementation plans.
    ├── reference/       -- Developer ground truth.
    └── user/            -- User-facing API documentation.
```

The exact current tree is documented in
`docs/reference/PROJECT_STRUCTURE.md`. The intended end state and phased work
are in `docs/plans/PROJECT_REFACTOR_PLAN.md`.

### Folder ownership

- `src/news/` owns the API, CLI, search pipeline, provider adapters, export
  formats, and runtime web/configuration helpers.
- `frontend/` owns the current HTML, CSS, and JavaScript browser interface.
- `scripts/` contains the ACLED OAuth bootstrap wrapper.
- `tests/` protects validation, filtering, deduplication, provider
  normalization, cache behavior, retries, exports, routes, CLI behavior, and
  frontend link safety.
- `docs/user/` explains the HTTP API.
- `docs/reference/` records the exact implemented structure.
- `docs/plans/` describes approved future structural work and is not a
  statement of current behavior.

## Part 3 -- Code Reference

- `pyproject.toml`
  - Defines Python dependencies, the `src` package layout, and the
    `news-server` and `news-search` commands.
- `config.toml`
  - Defines browser defaults and in-memory cache limits.
- `src/news/api/`
  - Owns FastAPI routes, query parsing, and response models.
- `src/news/search/`
  - Owns validation, filtering, deduplication, caching, and orchestration.
- `src/news/sources/`
  - Owns provider registration, concurrent fan-out, retry behavior, shared
    adapter infrastructure, and provider-specific adapters.
- `src/news/exports/`
  - Owns CSV, JSON, and SQLite serialization.
- `src/news/cli/`
  - Owns terminal parsing, API/direct fetch paths, rendering, and export flow.
- `src/news/web/`
  - Currently resolves repository-root configuration and frontend paths.
- `frontend/`
  - See `frontend/GUIDE_frontend.md`.
- `scripts/`
  - See `scripts/GUIDE_scripts.md`.
- `tests/`
  - See `tests/GUIDE_tests.md`.

## Part 4 -- Short Journal

- 2026-07-26: Removed the notebook research workspace, Jupyter dependencies, empty placeholder folders, and completed historical plans; future cleanup follows `docs/plans/PROJECT_REFACTOR_PLAN.md`.
