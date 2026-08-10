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
- A sign-in account and provider credentials from `.env` in the data directory,
  created from `.env.example`. The data directory is `NEWS_DATA_DIR` when set
  and the working directory otherwise.
- Browser, cache, and proxy-trust settings from an explicit server option,
  `NEWS_CONFIG`, a current-directory `config.toml`, or packaged defaults, in
  that order.
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
2. Startup hashes the sign-in password, checks the hash against it, and stores
   only the hash. A missing account leaves every data route closed.
3. Startup combines the selected operator settings with the packaged defaults,
   validates them, and creates a process-local cache.
4. The caller proves the account: a browser through the sign-in form, which
   leaves a session cookie, and a program through an HTTP Basic header.
5. The browser or CLI sends one validated search request.
6. The search package checks whether the same request is already in its short-
   lived memory cache.
7. If it is not cached, the selected sources are queried in parallel.
8. Each source response is converted to the common article format.
9. Local filters apply the same language, phrase, term, and domain rules to all
   sources.
10. Optional duplicate removal first groups identical canonical URLs, then
    obvious same-day copies with the same headline.
11. The final source page is sorted and returned through the API.
12. The browser displays the active date boundary and download links. The CLI
    can print a table, JSON, or JSONL and write export files.

In Docker, the server listens on all container interfaces on port 8000, while
Compose publishes it only on host loopback at port 50023. The optional Docker
CLI service and a reverse proxy on the external `single` network can reach the
container without widening the host port.

### Sign-in model

One shared account protects everything that returns news. The operator writes a
plain account name and password into `.env`; startup turns the password into a
PBKDF2 hash, stores only that, and re-verifies it on every boot. Failed
attempts are counted per client address and a run of them refuses that address
for a while, through both the form and the header. Sessions and counters live
in files, so a restart does not sign everyone out and does not reset a limit.
Three routes stay open because none reveal results: the sign-in page, the
browser's own static files, and the health check.

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
- The Docker health check requests the open health route, so a container with
  no signed-in browser is still reported as healthy. Persistent configuration
  is copied from the repository defaults only on first boot.
- Sign-in is one shared account with no second factor and no per-user
  permissions. It protects the data and the provider quotas; it is not an
  access-control system for several people.
- The plain password stays in `.env` on disk. File permissions and a private
  data directory are the protection, and that is a deliberate trade-off for not
  needing a hashing command.

## Local conventions

- Use `uv` for Python commands and dependency management.
- Keep the frontend dependency-light.
- Store the sign-in account and provider credentials in `.env`.
- Keep project docs in sync after code changes.
- Treat this project as a retrieval tool, not an analytics system.
- Keep Docker ports private and put a virtual private network or a Transport
  Layer Security reverse proxy in front for remote agents, then set
  `NEWS_SERVER_URL`. The password travels in plain text without that layer.
