# GUIDE_tests

## Part 1 -- Conceptual Explanation

### Purpose

The test tree mirrors production responsibilities so a failure points to the
part of the system that owns it. Default tests are deterministic and offline.
Live source behavior is excluded because credentials, network conditions, rate
limits, and changing source records would make the core suite unreliable.

Hashing a password is deliberately slow, so the shared account's hash is
computed once per test process in `fixtures/authentication.py` and written
straight into each temporary data directory. Route tests attach a session
cookie directly instead of posting the sign-in form; the tests that must
exercise the real password path do so explicitly.

The suite protects:

- API routes, settings startup, and error messages;
- sign-in, sign-out, failed-attempt limits, and password storage;
- sessions shared between worker processes, and the ceilings on state that an
  unauthenticated caller can add to;
- browser protection headers on every kind of response;
- the rule that provider keys never reach a log file;
- CLI parsing and output;
- export formats and local database cleanup;
- request validation, filtering, duplicate removal, caching, and coordination;
- OAuth, retry code, and individual source adapters;
- browser link safety and wheel-installed runtime assets.
- Docker build, bind, persistence, and entrypoint contracts.

Shared builders live in `fixtures/` and are named for the data they create.
There is no catch-all helper module.

## Part 2 -- Folder Tree and File Map

```text
tests/
├── GUIDE_tests.md
├── test_docker_setup.py
├── api/
│   ├── test_app.py
│   ├── test_auth.py
│   ├── test_auth_state_limits.py
│   ├── test_config.py
│   ├── test_openapi_contract.py
│   ├── test_public_exports.py
│   ├── test_security_headers.py
│   ├── test_server_cli.py
│   └── test_sessions_across_processes.py
├── cli/
│   ├── test_cli.py
│   └── test_cli_authentication.py
├── exports/
│   └── test_formats.py
├── fixtures/
│   ├── authentication.py
│   └── search_results.py
├── search/
│   ├── test_cache.py
│   ├── test_concurrent_searches.py
│   ├── test_deduplication.py
│   ├── test_filters.py
│   ├── test_service.py
│   └── test_validation.py
├── sources/
│   ├── test_acled_oauth.py
│   ├── test_failure_logging.py
│   ├── test_retry.py
│   └── providers/
│       ├── test_acled.py
│       ├── test_gdelt.py
│       ├── test_guardian.py
│       ├── test_mediacloud.py
│       ├── test_newsapi.py
│       └── test_nyt.py
└── web/
    ├── test_credentials.py
    ├── test_forwarded_headers.py
    ├── test_passwords.py
    ├── test_static.py
    └── test_wheel_installation.py
```

Package marker files are omitted from the tree.

## Part 3 -- Code Reference

### API and configuration

- `api/test_app.py` checks the browser shell, JSON routes, search/export
  responses, validation errors, runtime resource resolution, and factory
  injection through offline provider dependencies.
- `api/test_auth.py` checks that data routes refuse a signed-out caller, that
  the form and header paths both work, that a form token cannot be replayed,
  that repeated failures ban the address through either path, that signing out
  needs its own token, and that a server with no account stays closed.
- `api/test_auth_state_limits.py` checks that spent failed-login records are
  dropped rather than accumulated, that a live ban survives that pruning, and
  that the pending sign-in form tokens stop at their ceiling.
- `api/test_security_headers.py` checks the protection headers on data routes,
  refused requests, the search page, and the static files, and that the HTTPS
  promise is sent only over HTTPS.
- `api/test_sessions_across_processes.py` points two instances at one data
  directory to stand in for two worker processes, then checks that a session
  and its sign-out token are recognized by both.
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

- `cli/test_cli.py` checks parser flags, structured-output and temporal-boundary
  help, API parameter mapping, multi-page aggregation, table output, and
  package entry points.
- `cli/test_cli_authentication.py` checks which settings become the request's
  sign-in details, that both the search route and the export download carry the
  account, and that a refused request names the two settings to fix instead of
  repeating a bare status code.
- `exports/test_formats.py` checks CSV, JSON, and SQLite contracts, including
  connection cleanup and duplicate handling.

### Search process

- `search/test_validation.py` checks request boundary parsing and failure cases.
- `search/test_filters.py` checks language normalization and stable sorting.
- `search/test_deduplication.py` checks cleaned URLs and full-field merging.
- `search/test_concurrent_searches.py` checks that identical requests running at
  the same moment query the sources once, that different requests still run
  separately, and that a caller giving up does not cancel the others.
- `search/test_service.py` checks provider-facing options, local processing,
  pagination metadata, and source reports through typed fake executors.
- `search/test_cache.py` checks expiry, eviction, invariants, and service
  integration.

### Sources

- `sources/test_acled_oauth.py` checks credential inputs, offline token
  requests, HTTP errors, response-key variants, clock injection, and dotenv
  updates.
- `sources/test_retry.py` checks timeout, HTTP 5xx, and HTTP 4xx retry rules.
- `sources/test_failure_logging.py` checks that a rejected provider key never
  reaches the log or the browser response. Several sources send the key as a
  query parameter, so the request address inside an HTTP error carries it.
- Each file under `sources/providers/` owns the adapter-specific normalization,
  availability, pagination, or pause checks for the source in its
  filename.

### Web and fixtures

- `web/test_static.py` checks security-sensitive article-link display plus
  historical cutoff labels, first-use guidance, reduced-motion support, and
  active-page export wiring. It also protects the semantic list used by the
  hero's research-feature badges.
- `web/test_passwords.py` checks the stored hash format, a fresh salt per hash,
  and the values that are rejected: damaged text, a wrong scheme, and a
  weakened iteration count.
- `web/test_credentials.py` checks that startup writes a verifiable hash,
  leaves an unchanged account alone, drops sessions when the password changes,
  removes the account when the settings disappear, and warns about the example
  password.
- `web/test_forwarded_headers.py` checks which peer may rename the client or
  claim an encrypted connection. Its addresses are deliberately routable ones:
  the documentation ranges such as `203.0.113.0/24` are reported as private by
  Python, so a test using them would prove nothing.
- `web/test_wheel_installation.py` builds and installs a clean wheel, then
  checks that `/` redirects when signed out and serves the page with an account,
  outside the source checkout.
- `fixtures/authentication.py` builds sign-in state in a temporary directory,
  reusing one password hash per test process.
- `fixtures/search_results.py` builds schema-complete results and provider
  responses shared across boundary and cache tests.
- `test_docker_setup.py` protects the loopback host port, Toronto time,
  persistent data mount, external network, image command, unprivileged
  container account, dropped privileges, read-only root filesystem, and
  first-boot configuration behavior without requiring a Docker daemon.
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
- 2026-07-29: Added deployment tests that do not need a Docker daemon because Docker socket access is not available in every development environment.
- 2026-08-08: Added a cross-source date-format test after one adapter silently emitted a datetime, which broke sorting and duplicate matching without failing its own source test.
- 2026-08-10: Added a test that the export download sends the account, after the command-line export path was found sending an anonymous request that every protected server refused.
- 2026-08-10: Added protection-header tests covering each kind of response, because the header set had been applied only to the sign-in page.
- 2026-08-10: Wrote the shared-session tests against two instances pointed at one directory, which is the cheapest way to reproduce what two worker processes see.
