# GUIDE_tests

## Part 1 -- Conceptual Explanation

### Purpose

The test tree mirrors production responsibilities so a failure points to the
boundary or subsystem that owns it. All default tests are deterministic and
offline. Live provider behavior is excluded because credentials, network
conditions, rate limits, and changing upstream records would make the core
suite unreliable.

The suite protects:

- API routes, settings startup, and error mapping;
- CLI parsing and output;
- export formats and local database cleanup;
- request validation, filtering, deduplication, caching, and orchestration;
- OAuth, retry infrastructure, and individual provider adapters;
- browser link safety and wheel-installed runtime assets.

Shared builders live in `fixtures/` and are named for the contract they create.
There is no catch-all helper module.

## Part 2 -- Folder Tree and File Map

```text
tests/
├── GUIDE_tests.md
├── api/
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_openapi_contract.py
│   ├── test_public_exports.py
│   └── test_server_cli.py
├── cli/
│   └── test_cli.py
├── exports/
│   └── test_formats.py
├── fixtures/
│   └── search_results.py
├── search/
│   ├── test_cache.py
│   ├── test_deduplication.py
│   ├── test_filters.py
│   ├── test_service.py
│   └── test_validation.py
├── sources/
│   ├── test_acled_oauth.py
│   ├── test_retry.py
│   └── providers/
│       ├── test_acled.py
│       ├── test_gdelt.py
│       ├── test_guardian.py
│       ├── test_mediacloud.py
│       ├── test_newsapi.py
│       └── test_nyt.py
└── web/
    ├── test_static.py
    └── test_wheel_installation.py
```

Package marker files are omitted from the tree.

## Part 3 -- Code Reference

### API and configuration

- `api/test_app.py` checks the browser shell, JSON routes, search/export
  responses, validation errors, runtime resource resolution, and factory
  injection through offline provider dependencies.
- `api/test_config.py` checks packaged defaults, partial overrides, immutable
  settings, malformed TOML, misspelled keys, source names, and cache limits.
- `api/test_openapi_contract.py` compares generated OpenAPI output with the
  checked-in schema.
- `api/test_public_exports.py` protects the intentional package-level import
  surfaces.
- `api/test_server_cli.py` starts the server boundary in a subprocess and
  verifies explicit configuration wins over a malformed current-directory
  file before application construction.

### CLI and exports

- `cli/test_cli.py` checks parser flags, API parameter mapping, table output,
  and package entry points.
- `exports/test_formats.py` checks CSV, JSON, and SQLite contracts, including
  connection cleanup and duplicate handling.

### Search pipeline

- `search/test_validation.py` checks request boundary parsing and failure cases.
- `search/test_filters.py` checks language normalization and stable sorting.
- `search/test_deduplication.py` checks canonical URLs and rich-field merging.
- `search/test_service.py` checks provider-facing options, local processing,
  pagination metadata, and source reports through typed fake executors.
- `search/test_cache.py` checks expiry, eviction, invariants, and service
  integration.

### Sources

- `sources/test_acled_oauth.py` checks credential inputs, offline token
  requests, HTTP errors, response-key variants, clock injection, and dotenv
  updates.
- `sources/test_retry.py` checks timeout, HTTP 5xx, and HTTP 4xx retry rules.
- Each file under `sources/providers/` owns the adapter-specific normalization,
  availability, pagination, or cooldown checks for the provider in its
  filename.

### Web and fixtures

- `web/test_static.py` checks security-sensitive article-link rendering.
- `web/test_wheel_installation.py` builds and installs a clean wheel, then
  requests `/` outside the source checkout.
- `fixtures/search_results.py` builds schema-complete results and provider
  responses shared across boundary and cache tests.

### How to run

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

## Part 4 -- Short Journal

- 2026-07-26: Organized tests by production responsibility and kept live provider checks outside the deterministic default suite.
