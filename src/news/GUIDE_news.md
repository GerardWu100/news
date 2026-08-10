# GUIDE_news

## Purpose

The `news` package implements historical news retrieval from several sources.

## Subpackages

- `api/`: FastAPI app, route models, and query parameter parsing.
- `search/`: validation, shared date handling, cache, filters, duplicate
  removal, sorting, and search details.
- `sources/`: source registry, parallel requests, retries, source adapters, and
  reusable ACLED OAuth setup.
- `exports/`: CSV, JSON, and SQLite writers.
- `cli/`: command parser, fetch paths, table/JSON/JSONL output, and command flow.
- `web/`: installed browser files, packaged defaults, settings-path helpers,
  and validated settings.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected sources, applies local filters and optional duplicate removal,
sorts the final page, and returns normalized articles plus search details.
The browser displays the inclusive date boundary and can download the visible
page. The CLI emits full search details in JSON or streams compact article-only
JSONL for later model work.
The API application owns the process-local cache and passes it into the search
service; low-level search modules do not read configuration files.

The application factory also accepts a provider executor and source-status
function. Production uses the registered adapters; tests supply offline fakes
without patching module globals.

Importing the API module does not construct a configured application.
`news-server` parses command arguments first, then the server invokes the
factory. This preserves the documented rule that `--config` takes precedence
even when a current-directory `config.toml` is invalid. The command also owns
the host, port, and development-only reload settings required by local and
container runtimes.

Before parsing CLI arguments, `news-search` loads the root `.env`. Its
`--server` value therefore defaults to `NEWS_SERVER_URL` when configured and
otherwise uses `http://localhost:8000`. An explicit `--server` remains the
one-call override. This keeps the same structured retrieval workflow usable
against a local process, Docker Compose service, or protected remote server.

## Public Imports

- `news.search` exports validated request/result types, the executor type, the
  request builder, search runner, and deduplication entry points.
- `news.sources` exports shared source models and parallel-search entry points,
  not individual adapters.
- `news.exports` exports CSV, JSON, and SQLite format functions.
- Root, API, CLI, and web package initializers intentionally export nothing;
  callers use explicit module paths for those boundaries.
