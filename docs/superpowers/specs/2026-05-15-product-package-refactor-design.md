# Product Package Refactor Design

## Purpose

Refactor the project into a package-first product structure that follows the
repository guidelines: reusable Python product code lives under `src/news/`,
while tests, frontend assets, notebooks, documentation, outputs, and scripts
stay outside `src/`.

The refactor preserves product capabilities, not old file paths. The current
root wrappers and `backend/` package may be removed after equivalent package
entry points work.

## Current State

The project is a historical multi-source news retrieval tool with:

- a FastAPI application in `backend/app.py`,
- search orchestration in `backend/search/`,
- provider adapters in `backend/sources/`,
- command-line behavior in `backend/cli/` plus root `cli.py`,
- export helpers in `backend/export.py`,
- a static browser frontend in `frontend/`,
- tests in `tests/`,
- API exploration notebooks in `API_explorer/`,
- and guide files that explain the current layout.

The current structure works, but `backend/` has become a broad product package
that mixes API routes, command-line behavior, exports, search orchestration, and
source adapters under one top-level name. The refactor should make ownership
clearer without redesigning the search product.

## Target Structure

```text
.
├── README.md
├── config.toml
├── pyproject.toml
├── src/
│   ├── GUIDE_src.md
│   └── news/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── models.py
│       │   └── params.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── fetch.py
│       │   ├── output.py
│       │   ├── parser.py
│       │   └── workflow.py
│       ├── exports/
│       │   ├── __init__.py
│       │   └── formats.py
│       ├── search/
│       │   ├── __init__.py
│       │   ├── cache.py
│       │   ├── deduplication.py
│       │   ├── errors.py
│       │   ├── filters.py
│       │   ├── models.py
│       │   ├── service.py
│       │   └── validation.py
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── common.py
│       │   ├── registry.py
│       │   ├── retry.py
│       │   └── providers/
│       │       ├── __init__.py
│       │       ├── acled.py
│       │       ├── gdelt.py
│       │       ├── guardian.py
│       │       ├── mediacloud.py
│       │       ├── newsapi.py
│       │       └── nyt.py
│       └── web/
│           ├── __init__.py
│           ├── config.py
│           └── paths.py
├── frontend/
├── tests/
├── docs/
├── API_explorer/
└── website/
```

## Architecture

### `news.api`

Owns the HTTP boundary.

- `app.py` creates and exposes the FastAPI app.
- `params.py` owns public query parameter parsing and conversion into validated
  search requests.
- `models.py` owns Pydantic response models for API serialization.

The API layer should stay thin: it maps HTTP inputs and errors to the reusable
search package, then serializes the result.

### `news.search`

Owns validated search behavior.

- Request validation remains framework-independent.
- The search service coordinates cache lookup, provider fan-out, local filters,
  deduplication, sorting, and metadata construction.
- Search errors remain project-owned exceptions so the API and CLI can map them
  at their own boundaries.

### `news.sources`

Owns upstream provider access.

- `base.py` contains shared article and provider option data structures.
- `registry.py` owns default provider construction and source-name lookup.
- `retry.py` and `common.py` own shared network and adapter plumbing.
- Provider-specific adapters move under `sources/providers/`.

This keeps the fan-out interface close to provider infrastructure while making
individual adapters easier to locate.

### `news.exports`

Owns export formatting.

- CSV, JSON, and SQLite export behavior moves out of the broad backend package
  into `exports/formats.py`.
- Existing output schemas and field meanings should remain stable.

### `news.cli`

Owns command-line behavior.

- Parser, fetch, output, and workflow modules move from `backend/cli/`.
- The CLI should use package imports only.
- No root `cli.py` compatibility wrapper is required.

### `news.web`

Owns project-root path and configuration loading.

- `paths.py` resolves the project root, `.env`, `config.toml`, and frontend
  directory from the installed source tree.
- `config.py` reads `config.toml`.

This prevents path assumptions from being scattered across API and CLI modules.

## Entry Points

Old commands do not need to survive.

The refactor should prefer package-based execution and project scripts:

- `uv run python -m news.api.app` starts the local FastAPI server.
- `uv run python -m news.cli.workflow "inflation" -s 2025-01-01 -e 2025-03-01`
  runs the search CLI.
- `pyproject.toml` may expose scripts such as `news-server` and `news-search`
  if doing so keeps local use simpler.

The implementation plan should pick one canonical server command and one
canonical CLI command, document them, and test them.

## Data Flow

1. Browser or CLI submits query, date window, source choices, and filters.
2. API or CLI boundary converts raw inputs into a validated `SearchRequest`.
3. `news.search.service.run_search` checks the request cache when enabled.
4. `news.sources.search_all_detailed` queries selected providers concurrently.
5. Provider adapters return normalized `Article` records.
6. Search applies local filters, optional deduplication, sorting, and metadata
   construction.
7. API returns JSON responses; CLI prints tables, JSON, or export files.
8. Export helpers serialize result rows to CSV, JSON, or SQLite.

## Behavior To Preserve

- Provider search across GDELT, MediaCloud, ACLED, New York Times, Guardian, and
  NewsAPI.
- Source status reporting and missing-credential handling.
- Validation of dates, date range length, page number, source names, sort modes,
  match modes, and provider-specific filter fields.
- Local filters for language, exact phrase, excluded terms, included domains,
  excluded domains, search scope, and keyword match mode.
- Optional deterministic deduplication.
- Provider-page pagination metadata.
- CSV, JSON, and SQLite export outputs.
- CLI output modes and export behavior.
- Static frontend serving and frontend API contract.

## Behavior Allowed To Change

- Import paths.
- File paths.
- Root command names.
- The existence of `backend/`, `main.py`, and `cli.py`.
- Documentation layout around backend internals.

## Testing Strategy

The refactor should be behavior-preserving and test-driven at the migration
level:

- Update imports in existing tests from `backend...` to `news...`.
- Remove tests that only protect old compatibility wrappers.
- Keep tests that protect user-facing behavior, validation, cache behavior,
  retry behavior, exports, CLI formatting, and FastAPI routes.
- Add focused tests for the new path/config module if path resolution moves out
  of API code.
- Run `uv run ruff check .`.
- Run `uv run python -m unittest discover -s tests -v`.
- Run the canonical CLI command with a small direct or mocked path when
  practical.
- Use FastAPI's test client for route smoke tests instead of requiring a live
  server for automated verification.

## Documentation Strategy

Update documentation in the same session as the refactor:

- `README.md` should describe the new run commands and package layout.
- `GUIDE_ROOT.md` should describe the new root workflow and folder map.
- `PROJECT_STRUCTURE.md` should show the new tree.
- Replace `backend/GUIDE_backend.md` with guide files under the new meaningful
  folders, especially `src/GUIDE_src.md` and guides for `src/news/` or major
  subpackages if they add clarity.
- `tests/GUIDE_tests.md` should reflect new import paths and verification
  targets.

## Migration Constraints

- Do not edit `mynotes.md`.
- Do not keep backward compatibility solely for old files.
- Keep non-product code outside `src/`.
- Use relative paths derived from the current file location.
- Keep scripts thin; reusable logic belongs inside `src/news/`.
- Update docs after code movement.
- Finish with verification and a git commit when implementation is complete.

## Open Decisions For The Implementation Plan

The implementation plan must decide:

- whether to expose `news-server` and `news-search` scripts in `pyproject.toml`,
- whether to keep one `src/news/GUIDE_news.md` guide or separate subpackage
  guides,
- the exact canonical local server command,
- and the exact canonical CLI command.

The recommended defaults are:

- add `news-server` and `news-search` scripts,
- keep `src/GUIDE_src.md` plus `src/news/GUIDE_news.md`,
- start the server with `uv run news-server`,
- and run the CLI with `uv run news-search`.
