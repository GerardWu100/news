# GUIDE_scripts

## Part 1 -- Conceptual Explanation

### Purpose

The `scripts/` folder holds thin, one-off helpers that sit outside the importable
`src/news/` product package. These scripts support provider exploration and
credential bootstrap workflows rather than the main search product.

### Main scripts

- `acled_oauth_token.py`: requests an ACLED OAuth token and persists bearer
  credentials to the root `.env`.
- `acled_bearer_read.py`: performs a sample ACLED bearer-authenticated read and
  writes JSON output under `notebooks/api_explorer/acled/outputs/`.

## Part 2 -- Code Reference

- `acled_oauth_token.py`
  - Resolves the project root from `scripts/` and writes token artifacts to
    `notebooks/api_explorer/acled/outputs/`.
- `acled_bearer_read.py`
  - Imports shared helpers from `acled_oauth_token.py` in the same folder.

Run from the repository root:

```bash
uv run python scripts/acled_oauth_token.py
uv run python scripts/acled_bearer_read.py
```

See `notebooks/api_explorer/acled/GUIDE_acled.md` for the full ACLED workflow.
