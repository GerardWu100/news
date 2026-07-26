# GUIDE_acled

## Part 1 - Conceptual Explanation (What, How, Why)

### Purpose

This folder documents and explores ACLED API usage for conflict-event retrieval.

### Logic spine

1. Read `API_USAGE.md` for auth + endpoint conventions.
2. Run `acled_oauth_token.py` to request OAuth token and store bearer token in root `.env`.
3. Run `acled_bearer_read.py` to query ACLED event data using bearer auth.
4. Run `acled_api_explorer.ipynb` preview/live cells for interactive bearer-auth flow checks.

### Inputs/outputs and invariants

- Inputs: ACLED credential fields from root `.env` and notebook query parameters.
- Outputs: `outputs/acled_oauth_token_response.json`, `outputs/acled_bearer_sample_response.json`, and `outputs/acled_bearer_notebook_response.json` when notebook live fetch succeeds.
- Invariant: if credentials are missing, notebook prints setup guidance instead of failing silently.
- Invariant: notebook live cell can load root `.env` when launched either from repository root or from `notebooks/api_explorer/acled`.

## Part 2 - Folder Tree and File Map

```text
acled/
├── GUIDE_acled.md
├── API_USAGE.md
├── acled_api_explorer.ipynb
└── outputs/
    └── .gitkeep
```

- `API_USAGE.md`: official link and API usage notes.
- `scripts/acled_oauth_token.py`: requests OAuth token and stores bearer token in root `.env`.
- `scripts/acled_bearer_read.py`: bearer-authenticated ACLED read with one refresh-token retry on 401.
- `acled_api_explorer.ipynb`: preview + live bearer-read notebook.
- `outputs/`: live payload storage.

## Part 3 - Code Reference (Names and Structure)

- `scripts/acled_oauth_token.py`:
  - `load_env_file(...)`: loads root `.env`.
  - `normalize_env_value(...)`: strips surrounding quotes from `.env` values when present.
  - `request_oauth_token(...)`: executes token POST request.
  - `update_or_append_env_key(...)`: writes bearer values into root `.env`.
  - `print_acled_auth_hints(...)`: prints doc-based guidance for 400/401/403/404 responses.
  - `persist_token_fields(...)`: stores access/refresh/expiry metadata into `.env`.
  - `main()`: orchestration for token acquisition and `.env` persistence.
- `scripts/acled_bearer_read.py`:
  - `request_data_with_bearer(...)`: bearer-auth GET request.
  - `refresh_access_token(...)`: refresh-token grant flow.
  - `persist_refreshed_token(...)`: updates `.env` after refresh.
  - `fetch_payload_with_optional_refresh(...)`: bearer read with one refresh retry on 401.
  - `main()`: loads credentials, fetches sample data, saves JSON output.
- Notebook cell 1: static capabilities + bearer endpoint preview.
- Notebook cell 2: bearer-token ACLED data request flow with project-root auto-discovery for `.env`, then response persistence to `notebooks/api_explorer/acled/outputs/`.

How to run:
- `uv run python scripts/acled_oauth_token.py`
- `uv run python scripts/acled_bearer_read.py`
- Open and run notebook cells in `acled_api_explorer.ipynb`.
