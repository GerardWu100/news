# GUIDE_OVERVIEW

## Purpose

This project searches several news sources over a chosen date range, turns their
records into one common article format, optionally removes repeated articles,
and makes the results available through a browser, a JSON API, and a CLI.

The product focuses on retrieval. It does not rank articles with a proprietary
relevance model, fetch full article pages, calculate market statistics, or run
backtests. Its job is to provide a clear, source-aware set of articles that a
person or a later research process can inspect.

The browser is for historical exploration. It shows the inclusive end date next
to each completed search so the information boundary stays visible. The CLI is
for repeatable machine use and can return a table, JSON, or JSONL. Neither
interface creates a trading signal.

## Project structure

```text
.
├── .agents/skills/ -- Workspace-only agent retrieval and summary instructions.
├── blog/           -- Local article source.
├── Dockerfile      -- Python 3.13 application image.
├── docker-compose.yml -- Self-hosted server and optional CLI client.
├── src/news/       -- Installable API, CLI, search, source, export, and browser package.
├── scripts/        -- Credential and OpenAPI generation commands.
├── tests/          -- Offline tests grouped by production responsibility.
└── docs/           -- Plans, reference material, and user documentation.
```

The exact tree is maintained in `docs/reference/PROJECT_STRUCTURE.md`.

## Inputs and outputs

### Inputs

- A query string.
- Inclusive start and end dates in `YYYY-MM-DD`.
- Optional source selection.
- Optional language, duplicate-removal, exact-phrase, excluded-term, and
  included/excluded-domain filters.
- Optional source ranking and source-specific section filters.
- Provider credentials from an optional `.env` in the process working
  directory, created from `.env.example`.
- Browser and cache settings from an explicit server option, `NEWS_CONFIG`, a
  current-directory `config.toml`, or packaged defaults, in that order.
- An optional local or remote server address from `--server` or
  `NEWS_SERVER_URL`.

### Outputs

- A normalized article list with fields such as title, URL, date, source,
  domain, language, summary, content, section, author, matched sources, and
  duplicate count.
- Search details for the current source page, duplicate-removal counts,
  page-navigation state, and one status report per source.
- CSV, JSON, or SQLite files for later work.
- Browser downloads for the exact visible source page and CLI JSONL with one
  normalized article per line.

## Architecture and data flow

1. The `news-server` command loads credentials, reads bind options, and asks
   the application factory to build the FastAPI app.
2. Startup combines the selected operator settings with the packaged defaults,
   validates them, and creates a process-local cache.
3. The browser or CLI sends one validated search request.
4. The search package checks whether the same request is already in its short-
   lived memory cache.
5. If it is not cached, the selected sources are queried in parallel.
6. Each source response is converted to the common article format.
7. Local filters apply the same language, phrase, term, and domain rules to all
   sources.
8. Optional duplicate removal first groups identical canonical URLs, then
   obvious same-day copies with the same headline.
9. The final source page is sorted and returned through the API.
10. The browser displays the active date boundary and download links. The CLI
    can print a table, JSON, or JSONL and write export files.

In Docker, the server listens on all container interfaces on port 8000, while
Compose publishes it only on host loopback at port 50023. The optional Docker
CLI service and an authenticated reverse proxy on the external `single` network
can reach the container without widening the host port.

## Reliability and operations

- Temporary connection errors, read timeouts, and HTTP 5xx responses are
  retried with increasing delays.
- A source that returns HTTP 429 keeps a short local cooldown so repeated
  requests fail quickly instead of sending more requests immediately.
- Every outbound request has explicit connection and read timeouts.
- A source failure is isolated; other sources can still return results.
- Invalid dates, unknown source names, and overly long date ranges are rejected
  before any network request begins.
- Bad configuration and invalid cache limits are rejected before the server
  accepts requests.

## Boundaries and assumptions

- Pages follow the source’s own pagination. They are not one globally merged
  sliding window.
- Cache entries live in one process and expire quickly.
- Direct CLI mode skips the cache so an ad hoc request gets fresh results.
- Publication-date filtering reduces look-ahead risk but does not prove when an
  article first became tradable information. Source timestamps, revisions,
  missing archives, and later model knowledge remain limitations.
- Duplicate removal is conservative and deterministic. It does not compare
  article meaning.
- Sources support different filters, so some advanced options apply only to
  some sources.
- Missing credentials do not crash the app; unavailable sources appear in the
  source status and search reports.
- Browser assets and baseline settings ship in the wheel, so runtime files do
  not depend on a repository checkout.
- The application factory accepts a cache, source executor, and source-status
  function. Tests can therefore use offline fakes without changing module
  globals.
- Public HTTP routes and response models are recorded in a generated OpenAPI
  schema and checked by tests.
- The Docker health check requests the configuration route. Persistent
  configuration is copied from the repository defaults only on first boot.

## Local conventions

- Use `uv` for Python commands and dependency management.
- Keep the frontend dependency-light.
- Store provider credentials in the root `.env`.
- Keep project docs in sync after code changes.
- Treat this project as a retrieval tool, not an analytics system.
- Keep unauthenticated Docker ports private; use a VPN or authenticated TLS
  reverse proxy for remote agents and set `NEWS_SERVER_URL`.
