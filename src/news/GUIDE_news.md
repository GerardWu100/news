# GUIDE_news

## Purpose

The `news` package is the product implementation for historical multi-source
news retrieval.

## Subpackages

- `api/`: FastAPI app, route models, and query parameter parsing.
- `search/`: validation, shared boundary parsing, cache, filtering, deduplication, sorting, and result metadata.
- `sources/`: source registry, fan-out, retry behavior, provider adapters, and
  reusable ACLED OAuth bootstrap behavior.
- `exports/`: CSV, JSON, and SQLite serialization.
- `cli/`: command-line parser, fetch paths, table/JSON/JSONL output rendering,
  and workflow orchestration.
- `web/`: installed static browser assets, packaged defaults, external
  configuration-path helpers, and immutable validated settings.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected providers, applies local filters and optional deduplication,
sorts the final page, and returns normalized article rows plus metadata.
The browser displays the inclusive date boundary and can download the visible
page. The CLI emits full metadata in JSON or streams compact article-only JSONL
for downstream model pipelines.
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
- `news.sources` exports shared provider models and fan-out entry points, not
  individual adapters.
- `news.exports` exports CSV, JSON, and SQLite format functions.
- Root, API, CLI, and web package initializers intentionally export nothing;
  callers use explicit module paths for those boundaries.
