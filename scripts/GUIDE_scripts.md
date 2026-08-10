# GUIDE_scripts

## Part 1 -- Conceptual Explanation

### Purpose

The `scripts/` folder holds small setup commands outside the importable
`src/news/` package. The source package owns the reusable ACLED request,
response checks, and `.env` update logic.

### Main scripts

- `acled_oauth_token.py`: requests an ACLED OAuth token and saves the bearer
  fields needed by the ACLED source to the root `.env`.
- `generate_openapi.py`: regenerates the checked-in HTTP API contract from the
  application routes and response models.

## Part 2 -- Code Reference

- `acled_oauth_token.py`
  - Resolves the project root from `scripts/`.
  - Loads OAuth login fields from `.env`.
  - Calls the reusable package function.
  - Turns input, network, and source errors into short terminal messages.
  - Prints masked token details after saving the token.
  - Deliberately does not save the raw OAuth response because it contains
    credentials.

Reusable behavior is in `src/news/sources/acled_oauth.py`. That module accepts
injected network and clock functions so its tests never use a live provider or
real credential.

- `generate_openapi.py`
  - Builds the configured application without starting a server.
  - Writes stable, sorted JSON to `docs/reference/openapi.json`.
  - Accepts `--output PATH` for review or tooling workflows.

Regenerate the public API definition from the repository root:

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
