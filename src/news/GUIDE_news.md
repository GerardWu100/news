# GUIDE_news

## Purpose

The `news` package is the product implementation for historical multi-source
news retrieval.

## Subpackages

- `api/`: FastAPI app, route models, and query parameter parsing.
- `search/`: validation, shared boundary parsing, cache, filtering, deduplication, sorting, and result metadata.
- `sources/`: source registry, fan-out, retry behavior, and provider adapters.
- `exports/`: CSV, JSON, and SQLite serialization.
- `cli/`: command-line parser, fetch paths, output rendering, and workflow orchestration.
- `web/`: installed static browser assets, packaged defaults, and external
  configuration-path helpers.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected providers, applies local filters and optional deduplication,
sorts the final page, and returns normalized article rows plus metadata.
