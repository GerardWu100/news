# GUIDE_scripts

## Part 1 -- Conceptual Explanation

### Purpose

The `scripts/` folder holds a credential bootstrap helper outside the
importable `src/news/` product package.

### Main scripts

- `acled_oauth_token.py`: requests an ACLED OAuth token and persists the bearer
  fields required by the ACLED provider to the root `.env`.

## Part 2 -- Code Reference

- `acled_oauth_token.py`
  - Resolves the project root from `scripts/`.
  - Reads the OAuth login fields from `.env`.
  - Updates `.env` with the bearer token, token type, expiry, refresh token,
    and acquisition time when those values are returned.
  - Deliberately does not save the raw OAuth response because it contains
    credentials.

Run from the repository root:

```bash
uv run python scripts/acled_oauth_token.py
```

The longer-term refactor plan moves this reusable logic into `src/news/` and
keeps this file as a thin command wrapper.

## Part 3 -- Short Journal

- 2026-07-26: Removed provider-exploration notebooks and stopped persisting raw OAuth responses to reduce stale research code and secret-bearing artifacts.
