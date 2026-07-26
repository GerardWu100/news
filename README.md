# News Search Engine

Historical multi-source news retrieval with a FastAPI API, a lightweight browser UI, and a CLI for search and export workflows. Product Python code lives in `src/news/`.

## Quick Start

```bash
uv sync
uv run news-server
uv run news-search "inflation" -s 2025-01-01 -e 2025-03-01
```

Copy `.env.example` to `.env` and fill in whichever provider credentials you
want to enable. Commands look for this optional file in the current working
directory. GDELT works without credentials; MediaCloud, ACLED, NYT, Guardian,
and NewsAPI require their respective keys or tokens.

```bash
cp .env.example .env
```

For ACLED, add the OAuth login fields and generate the short-lived bearer token:

```bash
uv run python scripts/acled_oauth_token.py
```

The server resolves configuration in this order: `news-server --config PATH`,
the `NEWS_CONFIG` environment variable, `config.toml` in the current working
directory, then package defaults.

## Documentation

- API reference: `docs/user/API_REFERENCE.md`
- Current refactoring plan: `docs/plans/PROJECT_REFACTOR_PLAN.md`
- Developer structure reference: `docs/reference/PROJECT_STRUCTURE.md`

## Verification

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```
