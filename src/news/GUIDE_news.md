# GUIDE_news

## Purpose

The `news` package implements Historical Market News Search. It retrieves
date-bounded market news from several providers and Google Trends search
interest for the same query and date window.

## Package map

- `api/`: FastAPI application, routes, request models, query parsing, and
  sign-in checks.
- `search/`: request validation, dates, cache, filters, deduplication, sorting,
  and search details.
- `sources/`: provider registry, parallel requests, retries, shared settings,
  and ACLED login.
- `trends/`: historical Google Trends retrieval, keyword conversion, request
  pacing, and as-of rescaling. See `trends/GUIDE_trends.md`.
- `exports/`: CSV, JSON, and SQLite writers.
- `cli/`: `news-search` and `news-trends` parsing, retrieval, and output.
- `web/`: packaged browser files, settings, password hashing, stored sign-in
  state, and request-security helpers.

## Sign-in

`web/credentials.py` reads up to three account pairs from `.env`:
`UI_USERNAME` / `UI_PASSWORD`, plus the `_2` and `_3` pairs. On every startup
it creates or refreshes `.ui_credentials.json`, which stores password hashes.
There is no separate hashing command.

`web/passwords.py` performs the slow password hash and constant-time check.
`api/auth.py` checks one hash even when the account name is wrong, so the
response time does not reveal which part of the login failed.

`web/auth_store.py` stores sessions, failed-attempt counters, and short-lived
sign-in form tokens in locked, atomically replaced JSON files. Sessions are
read from disk for each check rather than cached in memory. This lets several
server workers share sign-in state, at the cost of one small file read per
signed-in request. The sign-out token lives in the same record for the same
reason.

`web/security.py` controls response headers, client addresses, and HTTPS
detection. Forwarded headers are trusted only when enabled and when the direct
peer is local or private; otherwise any caller could fake an address and use
another caller's failed-attempt allowance.

`require_signed_in` protects data routes. `request_is_signed_in` lets the root
route redirect a signed-out browser to `/login`. `api/login_page.py` renders
that page because a static file cannot create its server-issued form token.

## Browser protection

`api/app.py` adds security headers in one middleware, so new routes receive
them automatically. Each page gets only the permissions it needs:

- the search page may load its own scripts and web fonts;
- `/docs` may load its stylesheet and fonts, but no script;
- the sign-in page uses only its inline stylesheet;
- JSON, CSV, and redirects need no page resources.

Inline scripts and inline style attributes are not allowed. The browser code
sets animation delays and chart colours through the element style property.
The search page (`/`) and documentation page (`/docs`) are routes, not public
files, and both require sign-in. The application factory accepts a
`LoginSessions` instance so tests can use a temporary data directory.

## Runtime flow

Browser and CLI input becomes one validated search request. The search service
queries the selected providers, applies local filters and optional
deduplication, sorts the page, and returns normalized articles with search
details. The browser shows the inclusive date boundary; the CLI can emit full
JSON or compact article-only JSON Lines. The API owns the process-local cache
and passes it to the search service; low-level search code does not read files
or configuration.

Identical requests arriving together share one provider run. Later callers wait
for the existing run and receive their own result copy. If one caller leaves,
the shared run continues for the others. This prevents a browser reload or two
simultaneous commands from spending provider limits twice.

The application factory accepts provider and source-status functions. Production
uses registered adapters; tests provide offline fakes without patching module
globals.

`news-server` parses `--config` before the application factory runs. Importing
the API module does not build a configured application, so an explicit config
path still wins over an invalid current-directory `config.toml`.

Before parsing arguments, `news-search` loads `.env`. Its `--server` default is
`NEWS_SERVER_URL`, or `http://localhost:8000` when that variable is absent. An
explicit `--server` overrides it. `--direct` skips the server and calls
providers locally.

## Search attention

`trends/` is separate from `sources/`. Providers return article records that
can be normalized, filtered, and deduplicated. Google Trends returns a relative
0-to-100 series, so placing it in the article registry would mix two different
data shapes. The route and `news-trends` command share the article search's
query and dates, while Google receives plain keywords because it accepts no
search operators.

Only historical windows are supported. Google scales each value against the
peak of the requested window. An `as_of` date drops later points and rescales
the remaining series to prevent later information from affecting earlier
values when Google returned hourly or daily points. Weekly, monthly, and
unknown-granularity series require a fresh fetch ending on the decision date,
because one labelled period can contain later observations. See
`trends/GUIDE_trends.md` for the measured example.

`news-search --all-pages` trusts provider pagination even when local filters
empty an intermediate page. It then removes duplicates across page boundaries
and aggregates provider reports so an early failure remains visible.

`api/app.py` creates one Trends client per application so request pacing is
shared. The route is synchronous because the client performs blocking HTTP and
waits between requests; FastAPI runs it in a worker thread. `news-trends`
calls Google directly and needs no server account.

## Failure reporting

A provider failure inside a successful search appears in `source_reports`,
including the provider's response reason after configured credentials are
removed. A server refusal never reaches the providers; `cli/fetch.py` reads the
server's `detail` message and reports it. The useful explanation is preserved
instead of showing only a status code or request address.

## Provider settings

Adapters are created once in `sources/registry.py`, so deployment settings are
held in the shared `SourceSettings` value from `sources/settings.py`. The API
installs it while building the application; the CLI's direct path installs it
in `cli/fetch.py`. Both read the `[sources]` table. Defaults keep tests usable
without extra setup.

`connect_timeout_seconds` includes the TLS handshake, which GDELT can make
slow. `mediacloud_collections` cannot be empty because MediaCloud rejects a
request with neither a collection nor an outlet.

## Public imports

- `news.search`: validated request/result types, request builders, search
  runners, executors, and deduplication entry points.
- `news.sources`: shared source models and parallel-search entry points, not
  individual provider adapters.
- `news.exports`: CSV, JSON, and SQLite writers.
- `news.trends`: result and client types, errors, window and keyword helpers,
  pacing, and as-of rescaling.
- Root, API, CLI, and web package initializers export nothing intentionally;
  use explicit module paths there.
