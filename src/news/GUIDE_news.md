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
- `cli/`: command-line parser, fetch paths, output rendering, and workflow orchestration.
- `web/`: installed static browser assets, packaged defaults, external
  configuration-path helpers, and immutable validated settings.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected providers, applies local filters and optional deduplication,
sorts the final page, and returns normalized article rows plus metadata.
The API application owns the process-local cache and passes it into the search
service; low-level search modules do not read configuration files.
