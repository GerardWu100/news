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
- Google Trends frame conversion, keyword validation, rate-limit retries,
  route serialization, and CLI rendering;
- browser link safety and wheel-installed runtime assets.
- Docker build, bind, persistence, and entrypoint contracts.

Shared builders live in `fixtures/` and are named for the contract they create.
There is no catch-all helper module.

## Part 2 -- Folder Tree and File Map

```text
tests/
├── GUIDE_tests.md
├── test_docker_setup.py
├── api/
│   ├── test_app.py
│   ├── test_config.py
│   ├── test_openapi_contract.py
│   ├── test_public_exports.py
│   ├── test_server_cli.py
│   └── test_trends_endpoints.py
├── cli/
│   ├── test_cli.py
│   └── test_trends_cli.py
├── exports/
│   └── test_formats.py
├── fixtures/
│   ├── search_results.py
│   └── trends_results.py
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
├── trends/
│   └── test_google.py
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
- `api/test_trends_endpoints.py` checks the three trends routes through an
  offline fake client, including 422 validation and 502 upstream mapping.

### CLI and exports

- `cli/test_cli.py` checks parser flags, structured-output and temporal-boundary
  help, API parameter mapping, multi-page aggregation, table output, and
  package entry points.
- `cli/test_trends_cli.py` checks news-trends subcommand parsing and table,
  JSON, and CSV rendering through the offline fake client.
- `exports/test_formats.py` checks CSV, JSON, and SQLite contracts, including
  connection cleanup and duplicate handling.

### Trends

- `trends/test_google.py` checks keyword validation, pytrends DataFrame
  conversion (daily, intraday, and empty frames; regions; related queries),
  and the rate-limit retry and error-wrapping rules, all offline.

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

- `web/test_static.py` checks security-sensitive article-link rendering plus
  point-in-time labels, guided first-use structure, reduced-motion support, and
  active-page export wiring. It also protects the semantic list used by the
  hero's research-feature badges.
- `web/test_wheel_installation.py` builds and installs a clean wheel, then
  requests `/` outside the source checkout.
- `fixtures/search_results.py` builds schema-complete results and provider
  responses shared across boundary and cache tests.
- `fixtures/trends_results.py` builds deterministic trends results and the
  offline fake client shared by the API and CLI trends tests.
- `test_docker_setup.py` protects the loopback host port, Toronto time,
  persistent data mount, external network, image command, and first-boot
  configuration behavior without requiring a Docker daemon.
- `sources/providers/test_article_date_contract.py` asserts across every
  adapter that `Article.date` is a bare `YYYY-MM-DD` string or empty. Sorting
  and same-day duplicate matching both compare that field as raw text, so a
  drifting adapter produces wrong output without raising, and only a
  cross-provider check catches it.

### How to run

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

## Part 4 -- Short Journal

- 2026-07-26: Organized tests by production responsibility and kept live provider checks outside the deterministic default suite.
- 2026-07-29: Added daemon-independent deployment contract tests because Docker socket access is not guaranteed in every development environment.
- 2026-08-08: Added a cross-provider date-format contract test after one adapter silently emitted a datetime, which broke sorting and duplicate matching without failing any per-provider test.
- 2026-08-09: Added offline trends coverage; live Google Trends behavior stays outside the default suite for the same reliability reasons as live providers.
