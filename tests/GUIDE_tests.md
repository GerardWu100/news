# GUIDE_tests

## Part 1 -- Conceptual Explanation

### Purpose

The `tests/` folder holds the local verification layer for the production app.
It focuses on deterministic logic that should remain stable in this workspace:

- request validation,
- local filtering,
- frontend static rendering safety,
- deduplication,
- export formatting,
- cache behavior,
- retry behavior,
- adapter normalization,
- route wiring,
- and installed-wheel runtime resources.

### Why these tests exist

The live providers depend on external services, credentials, rate limits, and
network availability. That makes them poor candidates for fast local regression
coverage. The project instead protects the parts most likely to break subtly
without requiring live API calls:

- validated request normalization,
- canonical URL logic,
- duplicate merging,
- source report metadata,
- export contracts,
- cache TTL and eviction behavior,
- retry rules for transient failures,
- FastAPI route contracts,
- CLI argument mapping,
- and resource cleanup checks for local exports.

## Part 2 -- Folder Tree and File Map

```text
tests/
├── GUIDE_tests.md         -- This documentation file.
├── test_acled_oauth.py    -- Offline OAuth request and persistence tests.
├── test_app.py            -- FastAPI route smoke tests.
├── test_cache.py          -- Cache TTL, eviction, and search-cache integration tests.
├── test_cli.py            -- CLI parser and table-rendering tests.
├── test_config.py         -- Typed configuration defaults and validation tests.
├── test_export.py         -- CSV, JSON, and SQLite export tests.
├── test_frontend_static.py -- Static checks for security-sensitive frontend rendering.
├── test_retry.py          -- Retry helper tests.
├── test_search_service.py -- Search-pipeline and adapter normalization tests.
└── test_wheel_installation.py -- Clean-wheel browser smoke test.
```

## Part 3 -- Code Reference

### `test_acled_oauth.py`

- Verifies required OAuth input fields and placeholder rejection.
- Verifies the encoded token request through an injected offline opener.
- Verifies HTTP errors remain available to the terminal wrapper.
- Verifies supported token-key variants and missing-token failures.
- Verifies deterministic timestamps and one-pass temporary dotenv updates.

### `test_app.py`

- Verifies the root route serves the frontend shell.
- Verifies config and source-status routes return JSON successfully.
- Verifies the search and export routes return the structured response contract.
- Verifies project-owned validation errors are mapped to HTTP 422 responses.
- Verifies runtime lookup uses package assets, explicit configuration paths,
  and packaged defaults.

### `test_search_service.py`

- `BuildSearchRequestTests`
  - Verifies invalid date ranges fail fast.
  - Verifies malformed dates are rejected.
  - Verifies unknown source names are rejected.
  - Verifies invalid advanced-search enum values are rejected.
  - Verifies validation raises `SearchValidationError` without importing FastAPI.
  - Verifies provider-aware advanced filters normalize into the expected structured request fields.
  - Verifies source names come from the explicit source registry.

- `DeduplicationTests`
  - Verifies tracking parameters are removed from canonical URLs.
  - Verifies duplicate records from multiple providers collapse correctly.
  - Verifies duplicate collapse preserves the richest summary/body/byline fields available across the duplicate group.

- `RunSearchTests`
  - Uses a fake executor to test filtering, deduplication, provider-page behavior, and metadata assembly without hitting live APIs.
  - Fake executors carry explicit `SourceSearchOptions` and source-name
    signatures so the tests document the production executor contract.

- `MediaCloudSourceTests` / `NewYorkTimesSourceTests`
  - Verify that a recent `429` puts the adapter into a local cooldown so follow-up requests fail fast.

- `MediaCloudPaginationTokenStoreTests`
  - Verifies MediaCloud pagination tokens expire and old query keys are evicted at capacity.

- `AdditionalSourceAdapterTests`
  - Verify Guardian, NYT, and NewsAPI normalization against the shared article schema.

### `test_export.py`

- Verifies CSV defaults and optional content inclusion.
- Verifies JSON export structure.
- Verifies SQLite schema behavior and duplicate handling.
- Verifies SQLite exports do not emit `ResourceWarning` after writing rows.

### `test_frontend_static.py`

- Verifies article-dialog links pass through `buildSafeArticleUrl(...)`.
- Verifies raw provider URLs are not inserted directly into `href` attributes.

### `test_cli.py`

- Verifies parser defaults and supported flags.
- Verifies CLI-to-API parameter mapping.
- Verifies the plain-text table renderer.
- Verifies `pyproject.toml` exposes the `news-server` and `news-search` package scripts.

### `test_cache.py`

- Verifies TTL expiry.
- Verifies oldest-entry eviction when the cache is full.
- Verifies `run_search(...)` reuses cached results for identical requests.
- Verifies `run_search(...)` does not bind the default cache object in its signature.
- The cache integration fake executor is typed to match the production search
  executor shape.

### `test_config.py`

- Verifies an absent optional file uses packaged defaults.
- Verifies partial operator files override only selected values.
- Verifies malformed TOML, misspelled keys, unknown source names, and invalid
  cache limits fail clearly.
- Verifies the resulting settings objects are immutable.

### `test_retry.py`

- Verifies timeouts are retried.
- Verifies HTTP 5xx responses are retried.
- Verifies HTTP 4xx responses fail immediately.

### `test_wheel_installation.py`

- Builds the wheel into a temporary directory.
- Installs it and its dependencies into a clean temporary environment.
- Requests `/` from the installed application outside the source checkout.

### How to run

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```
