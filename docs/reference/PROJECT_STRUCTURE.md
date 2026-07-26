# PROJECT_STRUCTURE

## Directory Tree

```text
.
├── .env
├── .gitignore
├── .python-version
├── README.md
├── config.toml
├── pyproject.toml
├── uv.lock
├── GUIDE_ROOT.md
├── GUIDE_OVERVIEW.md
├── src/
│   ├── GUIDE_src.md
│   └── news/
│       ├── GUIDE_news.md
│       ├── __init__.py
│       ├── api/
│       ├── cli/
│       ├── exports/
│       ├── search/
│       ├── sources/
│       └── web/
├── frontend/
│   ├── GUIDE_frontend.md
│   ├── index.html
│   ├── styles.css
│   └── scripts/
├── scripts/
│   ├── acled_oauth_token.py
│   └── acled_bearer_read.py
├── tests/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── outputs/
│   ├── reports/
│   ├── figures/
│   └── runs/
├── notebooks/
│   └── api_explorer/
│       ├── GUIDE_api_explorer.md
│       ├── acled/
│       ├── gdelt/
│       ├── mediacloud/
│       └── commoncrawl/
├── docs/
│   ├── user/
│   │   └── API_REFERENCE.md
│   └── reference/
│       └── PROJECT_STRUCTURE.md
└── logs/
```

## File Descriptions

- `config.toml`: frontend defaults plus cache TTL and capacity settings.
- `pyproject.toml`: dependencies, package metadata, `src` package discovery, and command scripts.
- `README.md`: concise entry point with quick start and links to detailed docs.

- `src/news/api/app.py`: FastAPI routes for config, source status, search, and export.
- `src/news/api/models.py`: Pydantic response models for the public API.
- `src/news/api/params.py`: HTTP query parameter parsing and search-request conversion.
- `src/news/exports/formats.py`: CSV, JSON, and SQLite export helpers.
- `src/news/cli/parser.py`: CLI parser and API parameter mapping.
- `src/news/cli/fetch.py`: CLI HTTP API and direct package fetch paths.
- `src/news/cli/output.py`: CLI table rendering and export writing.
- `src/news/cli/workflow.py`: CLI orchestration and boundary error handling.
- `src/news/search/cache.py`: in-memory TTL cache for validated search requests.
- `src/news/search/errors.py`: project-owned validation exception.
- `src/news/search/service.py`: orchestration layer for filtering, deduplication, cache use, and response metadata.
- `src/news/search/validation.py`: strict request normalization and validation.
- `src/news/sources/common.py`: shared hostname, date, and cooldown helpers for adapters.
- `src/news/sources/registry.py`: source adapter construction and source-name lookup.
- `src/news/sources/retry.py`: shared timeout and retry helpers for provider requests.
- `src/news/sources/__init__.py`: concurrent fan-out and user-facing source error mapping.
- `src/news/sources/providers/`: provider-specific adapters for ACLED, GDELT, Guardian, MediaCloud, NewsAPI, and NYT.
- `src/news/web/config.py`: TOML configuration loading.
- `src/news/web/paths.py`: project-root resource path resolution.

- `frontend/index.html`: HTML shell for the search UI and results area.
- `frontend/styles.css`: warm editorial theme, layout, cards, and responsive rules.
- `frontend/scripts/app.js`: page orchestration, submission, pagination, and share-link behavior.
- `frontend/scripts/form.js`: form reading, URL hydration, URL sync, and clipboard helpers.
- `frontend/scripts/render.js`: DOM rendering for meta text, status chips, results, and the article dialog.
- `frontend/scripts/state.js`: in-memory state container for the active search.

- `scripts/acled_oauth_token.py`: ACLED OAuth token bootstrap helper.
- `scripts/acled_bearer_read.py`: ACLED bearer-authenticated sample data read helper.

- `tests/test_app.py`: FastAPI route smoke tests.
- `tests/test_search_service.py`: validation, deduplication, pipeline, and adapter tests.
- `tests/test_export.py`: export formatter tests.
- `tests/test_frontend_static.py`: static checks for frontend link-sanitization helpers.
- `tests/test_cli.py`: CLI parser, package script, and table-rendering tests.
- `tests/test_cache.py`: cache TTL, eviction, and integration tests.
- `tests/test_retry.py`: retry helper tests.

- `docs/user/API_REFERENCE.md`: endpoint and query-parameter reference.

## Subfolder Purposes

- `src/news/`: importable product package for API, CLI, search, exports, source adapters, and runtime config/path helpers.
- `frontend/`: browser-based search interface with shareable URL state.
- `scripts/`: thin one-off helpers that call package or upstream APIs.
- `tests/`: local regression and smoke verification.
- `data/`: raw, interim, and processed datasets for research workflows.
- `outputs/`: CLI exports, reports, figures, and run artifacts.
- `notebooks/api_explorer/`: notebook-first upstream API exploration workspace.
- `docs/user/`: user-facing documentation.
- `docs/reference/`: developer reference material including this file.
- `logs/`: runtime log files.
