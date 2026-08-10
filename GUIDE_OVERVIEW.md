# GUIDE_OVERVIEW

## Summary and Purpose

This project is a historical multi-source news retrieval system. Its job is to
search several upstream providers over a date window, normalize the returned
records into one shared schema, optionally collapse duplicates, and expose the
results through:

- a browser UI,
- a JSON API,
- and a CLI with export support.

The product is retrieval-first. It does not rank by proprietary relevance
models, crawl article bodies, or compute page-level analytics. The value is a
clean, provider-aware search and export workflow for research.

Alongside articles, the package also retrieves Google Trends relative
search-interest data (a 0-100 index of how much people searched a term)
through dedicated `/api/trends/*` routes and the `news-trends` command. That
data lives outside the article search pipeline because it is a time series,
not a set of records to filter and deduplicate.

The browser emphasizes human point-in-time exploration: its inclusive end date
is shown as an information boundary beside every completed result set. The CLI
emphasizes reproducible machine use with table, JSON, and JSONL output. Neither
interface performs signal generation or backtesting; exports feed those
downstream workflows.

## Project Structure

```text
.
├── .agents/skills/ -- Workspace-only agent retrieval and summary workflow.
├── blog/           -- Local-only article source.
├── Dockerfile      -- Reproducible Python 3.13 application image.
├── docker-compose.yml -- Persistent self-hosted server and optional CLI client.
├── src/news/       -- Installable API, CLI, search, source, trends, export, and web package.
├── scripts/        -- Thin credential and OpenAPI generation commands.
├── tests/          -- Offline tests organized by production responsibility.
└── docs/           -- Completed plans, exact reference material, and user docs.
```

The exact implemented tree is maintained in
`docs/reference/PROJECT_STRUCTURE.md`.

## Inputs and Outputs

### Inputs

- A query string.
- Inclusive start and end dates in `YYYY-MM-DD`.
- Optional source selection.
- Optional language, deduplication, exact-phrase, exclude-term, and
  include/exclude-domain filters.
- Optional provider ranking mode and provider-specific section filters.
- Provider credentials from an optional `.env` in the process working
  directory, created from `.env.example`.
- Frontend and cache settings from an explicit server option, `NEWS_CONFIG`,
  current-directory `config.toml`, or packaged defaults, in that order.
- An optional local or remote server base URL from `--server` or
  `NEWS_SERVER_URL`.

### Outputs

- A normalized article list with fields such as title, URL, date, source,
  domain, language, summary, content, section, author, matched sources, and
  duplicate count.
- Search metadata describing the current provider page, duplicate-removal
  counts, pagination state, and per-source execution reports.
- CSV, JSON, or SQLite exports for downstream workflows.
- Browser downloads for the exact visible provider page and CLI JSONL with one
  normalized article per line.

## Architecture and Data Flow

1. The `news-server` command loads credentials, parses bind options, and asks
   the application factory to construct the FastAPI app.
2. Startup merges the selected operator configuration over packaged defaults,
   validates it, and constructs the process-local cache.
3. The browser or CLI submits a validated request.
4. The search package checks whether the same request is already available in a short
   in-memory cache.
5. If not cached, requested providers are queried concurrently.
6. Each provider response is normalized into the common article schema.
7. Local filtering applies shared rules such as language, exact-phrase,
   exclude-term, and domain filtering.
8. Optional deduplication collapses canonical-URL matches first, then obvious
   same-day syndicated headline matches.
9. The final provider page is sorted and returned through the API.
10. The browser renders the page with its active date boundary and exact-page
    download links. The CLI can print table, JSON, or JSONL and export files.

In Docker, the server binds to all container interfaces on port 8000 while
Compose publishes it only to host loopback on port 50023. Both the optional
Docker CLI service and authenticated reverse proxies on the external `single`
network can reach the container without widening the host bind.

## Reliability and Operational Behavior

- Transient connection errors, read timeouts, and HTTP 5xx responses are
  retried with exponential backoff.
- Known rate-limited providers keep a local cooldown window after HTTP 429 so
  repeated requests fail fast instead of hammering the upstream API.
- Every outbound request uses explicit connect and read timeouts.
- Source failures are isolated. One provider can fail while the rest still
  return usable results.
- Invalid dates, unknown source names, and oversized date ranges are rejected
  before any outbound network work starts.
- Malformed or misspelled configuration and invalid cache limits are rejected
  before the server accepts requests.

## Product Boundaries and Assumptions

- Pagination is provider-page based, not a globally merged sliding window.
- Cache entries are process-local and intentionally short-lived.
- Direct CLI mode bypasses the cache so ad hoc pulls stay fresh.
- Publication-date filtering reduces look-ahead risk but does not prove when an
  article first became tradable information. Provider timestamps, revisions,
  missing archives, and downstream model knowledge remain research limitations.
- Deduplication is conservative and deterministic; it does not perform fuzzy
  semantic matching.
- Providers expose asymmetric upstream filters, so some advanced options apply
  only to some sources.
- Missing credentials do not crash the app; unavailable providers are surfaced
  in source status and source reports.
- Browser assets and baseline configuration ship in the wheel, so runtime
  resources do not depend on a repository checkout.
- Application construction accepts injected cache, provider executor, and
  source-status dependencies, which keeps route tests isolated and offline.
- Public HTTP routes and response models are captured in a generated,
  contract-tested OpenAPI schema.
- The Docker health check probes the configuration route. Persistent
  configuration is copied from repository defaults only on first boot.

## User Overrides

- Use `uv` workflows.
- Keep the frontend dependency-light.
- Store provider credentials in the root `.env`.
- Keep project docs in sync after code changes.
- Treat the project as a retrieval tool rather than an analytics surface.
- Keep unauthenticated Docker ports private; remote agents use a VPN or
  authenticated TLS reverse proxy and configure the CLI with
  `NEWS_SERVER_URL`.
