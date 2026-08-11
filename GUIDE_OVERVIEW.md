# GUIDE_OVERVIEW

## Purpose

This project searches several news sources over a chosen date range, turns their
records into one common article format, optionally removes repeated articles,
and makes the results available through a browser, a JSON API, and a CLI. It
also returns one signal alongside the articles: how much the public searched
for the same keywords during the same days.

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
├── src/news/       -- Installable API, CLI, search, source, trends, export, and browser package.
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
- For search attention, the same query and dates, an optional geography, and an
  optional decision date inside the window.
- Sign-in accounts (at most three) and provider credentials from `.env` in the
  data directory, created from `.env.example`. The data directory is
  `NEWS_DATA_DIR` when set and the working directory otherwise.
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
- A search-attention series for the same window: dated points, one value per
  keyword, the point spacing that arrived, and the window and anchor date those
  values are scaled against.

## Architecture and data flow

1. The `news-server` command loads credentials, reads bind options, and asks
   the application factory to build the FastAPI app.
2. Startup hashes each configured sign-in password, checks the hash against it,
   and stores only the hashes. Settings without one complete account leave
   every data route closed.
3. Startup combines the selected operator settings with the packaged defaults,
   validates them, and creates a process-local cache.
4. The caller proves the account: a browser through the sign-in form, which
   leaves a session cookie, and a program through an HTTP Basic header.
5. The browser or CLI sends one validated search request.
6. The search package checks whether the same request is already in its short-
   lived memory cache, and then whether an identical request is already
   running. A second caller joins the search in flight rather than spending the
   provider rate limits twice.
7. If neither applies, the selected sources are queried in parallel.
8. Each source response is converted to the common article format.
9. Local filters apply the same language, phrase, term, and domain rules to all
   sources.
10. Optional duplicate removal first groups identical canonical URLs, then
    obvious same-day copies with the same headline.
11. The final source page is sorted and returned through the API.
12. The browser displays the active date boundary and download links. The CLI
    can print a table, JSON, or JSONL and write export files.

Search attention runs on a separate, simpler path. The same query is reduced to
plain keywords, because the attention source accepts no boolean operators, and
the same start and end dates become the requested window. One request goes out,
spaced from the previous one so the unofficial endpoints do not refuse a burst,
and the result is optionally rescaled to a chosen decision date before it is
returned. There is no cache, no duplicate removal, and no merging across
sources, because none of those apply to a single time series.

In Docker, the server listens on all container interfaces on port 8000, while
Compose publishes it only on host loopback at port 50023. The optional Docker
CLI service and a reverse proxy on the external `single` network can reach the
container without widening the host port.

### Sign-in model

Up to three accounts protect everything that returns news. The operator writes
plain account names and passwords into `.env`, one required pair and two
optional numbered pairs; startup turns each password into a PBKDF2 hash, stores
only the hashes, and re-verifies them on every boot. The accounts separate
people, not permissions: any of them opens every route. Failed
attempts are counted per client address and a run of them refuses that address
for a while, through both the form and the header. Sessions and counters live
in files read and written under a lock, so a restart does not sign everyone out,
a limit is not reset, and several server processes agree about who is signed in.
Three routes stay open because none reveal results: the sign-in page, the
browser's own static files, and the health check.

Anything a caller can add to without proving the account is bounded: the
failed-attempt file drops records once their window and ban have passed, and
the sign-in form tokens held in memory have a ceiling. Proxy headers naming a
different client are believed only when the machine that opened the connection
is itself local or private, so the failed-attempt limit cannot be sidestepped
by setting a header.

Every response carries browser protection headers, attached in one place rather
than route by route. Article text comes from outside sources and is rendered as
inert text, and the Content Security Policy allows no inline script or style,
so injected markup has nothing to execute.

### What the attention numbers are, and are not

They are a relative index from 0 to 100, never counts. The value 100 marks the
busiest moment inside the window that was requested, and everything else is
scaled against it, so the same day can read very differently depending on how
far past it the request reached. Two series fetched over different windows are
not comparable, and a zero can mean the term was too rare to report rather than
unsearched.

That scaling hides a form of look-ahead bias the project's date filter cannot
catch: the divisor is the peak of the whole window, including days after the
one being read, so a long window tells its early days about a spike that had
not happened yet. Supplying a decision date drops the later points and rescales
to what was known then. Features built on ratios or changes survive the
original scaling because it is a single constant multiplier; features that
compare levels against a fixed threshold do not.

## Reliability and operations

- Temporary connection errors, read timeouts, and HTTP 5xx responses are
  retried with increasing delays.
- A source that returns HTTP 429 keeps a short local cooldown so repeated
  requests fail quickly instead of sending more requests immediately.
- Every outbound request has explicit connection and read timeouts.
- Attention requests are spaced by a configured minimum gap and retried once
  after a rate-limit refusal, because those endpoints are unofficial and
  answer a burst with a refusal that lasts.
- A source failure is isolated; other sources can still return results.
- Invalid dates, unknown source names, and overly long date ranges are rejected
  before any network request begins.
- Bad configuration and invalid cache limits are rejected before the server
  accepts requests.

## Boundaries and assumptions

- Pages follow the source’s own pagination. They are not one globally merged
  sliding window.
- Cache entries live in one process and expire quickly. Sharing between
  identical requests running at the same moment is also per process, so two
  worker processes can still each query the sources once.
- Direct CLI mode skips the cache so an ad hoc request gets fresh results.
- Publication-date filtering reduces look-ahead risk but does not prove when an
  article first became tradable information. Source timestamps, revisions,
  missing archives, and later model knowledge remain limitations.
- Duplicate removal is conservative and deterministic. It does not compare
  article meaning.
- Sources support different filters, so some advanced options apply only to
  some sources.
- The attention source is reached through an unmaintained third-party library
  calling private endpoints. It works today and could stop without warning, so
  it sits behind a one-method interface that can be swapped in one file. Only
  the window-based capability is used; everything describing the present moment
  is out of scope and has been removed by the provider in any case.
- A fetch of a past window today is not what the same request would have
  returned then, because the provider recomputes from its current sample. A
  decision date fixes the scaling, not that revision risk.
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
- Sign-in allows at most three accounts, with no second factor and no
  per-account permissions. They protect the data and the provider quotas and
  let separate people hold separate passwords; they are not an access-control
  system, because every account reaches everything.
- The plain passwords stay in `.env` on disk. File permissions and a private
  data directory are the protection, and that is a deliberate trade-off for not
  needing a hashing command.

## Local conventions

- Use `uv` for Python commands and dependency management.
- Keep the frontend dependency-light.
- Store the sign-in accounts and provider credentials in `.env`.
- Keep project docs in sync after code changes.
- Treat this project as a retrieval tool, not an analytics system.
- Keep Docker ports private and put a virtual private network or a Transport
  Layer Security reverse proxy in front for remote agents, then set
  `NEWS_SERVER_URL`. The password travels in plain text without that layer.
