# GUIDE_scripts

## Part 1 -- Conceptual Explanation

### Purpose

The `scripts/` folder holds a thin credential-bootstrap command outside the
importable `src/news/` product package. Reusable ACLED request, response
validation, and dotenv persistence behavior lives in the source package.

### Main scripts

- `acled_oauth_token.py`: requests an ACLED OAuth token and persists the bearer
  fields required by the ACLED provider to the root `.env`.
- `generate_openapi.py`: regenerates the checked-in HTTP API contract from the
  application routes and response models.

## Part 2 -- Code Reference

- `acled_oauth_token.py`
  - Resolves the project root from `scripts/`.
  - Loads OAuth login fields from `.env`.
  - Calls the reusable package workflow.
  - Maps input, network, and provider errors to concise terminal messages.
  - Prints masked token metadata after successful persistence.
  - Deliberately does not save the raw OAuth response because it contains
    credentials.

Reusable behavior is in `src/news/sources/acled_oauth.py`. That module accepts
injected network and clock functions so its tests never use a live provider or
real credential.

- `generate_openapi.py`
  - Constructs the configured application without starting a server.
  - Writes stable, sorted JSON to `docs/reference/openapi.json`.
  - Accepts `--output PATH` for review or tooling workflows.

Regenerate the public contract from the repository root:

```bash
uv run python scripts/generate_openapi.py
```

Run from the repository root:

```bash
uv run python scripts/acled_oauth_token.py
```

## Part 3 -- Short Journal

- 2026-07-26: Removed provider-exploration notebooks and stopped persisting raw OAuth responses to reduce stale research code and secret-bearing artifacts.
- 2026-07-26: Kept OAuth as a script rather than adding a third package command because token bootstrap is an occasional setup workflow.
