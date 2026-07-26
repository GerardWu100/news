# ACLED API Usage

Official site:
- https://acleddata.com/

Authentication:
- OAuth token flow with:
  - `POST https://acleddata.com/oauth/token`
  - `Content-Type: application/x-www-form-urlencoded`
  - fields: `username`, `password`, `grant_type=password`, `client_id=acled`
- ACLED data requests should use bearer authorization header:
  - `Authorization: Bearer <ACLED_BEARER_TOKEN>`

Environment setup in root `.env`:
- `ACLED_OAUTH_TOKEN_URL`
- `ACLED_OAUTH_GRANT_TYPE`
- `ACLED_OAUTH_CLIENT_ID`
- `ACLED_USERNAME`
- `ACLED_PASSWORD`

Credential formatting note:
- Prefer unquoted values in `.env` (for example `ACLED_USERNAME=user@example.com`).

Base endpoint:
- `https://acleddata.com/api/acled/read`

Typical workflow:
1. Request OAuth token from `https://acleddata.com/oauth/token`.
2. Build query parameters (`event_date`, `country`, `event_type`, `limit`, etc.).
3. Send ACLED data request with bearer-token authentication.
4. Parse returned JSON and inspect event rows.

Example query shape:
- `event_date=2025-01-01|2025-01-31`
- `country=Ukraine`
- `limit=10`

Notebook in this folder:
- `acled_api_explorer.ipynb` prints preview parameters and attempts live fetch when credentials are set.
- The notebook now auto-discovers root `.env` by searching upward from the current working directory, so it works from both:
  - workspace root (`/Users/gwh/projects/news`)
  - notebook folder (`notebooks/api_explorer/acled`)
- Live payloads are written to `notebooks/api_explorer/acled/outputs/` on successful requests.

Script for OAuth token + bearer flow:
- `scripts/acled_oauth_token.py`
- Run: `uv run python scripts/acled_oauth_token.py`
- Behavior:
  1. Reads ACLED OAuth fields from root `.env`.
  2. Sends `POST` token request with `application/x-www-form-urlencoded`.
  3. Saves raw token response to `outputs/acled_oauth_token_response.json`.
  4. Stores `ACLED_BEARER_TOKEN` and `ACLED_BEARER_TOKEN_TYPE` back into root `.env`.
  5. Prints bearer header format for later API calls.

Script for bearer-authenticated reads:
- `scripts/acled_bearer_read.py`
- Run: `uv run python scripts/acled_bearer_read.py`
- Behavior:
  1. Reads `ACLED_BEARER_TOKEN` from root `.env`.
  2. Calls `https://acleddata.com/api/acled/read` with bearer authorization.
  3. On HTTP `401`, attempts refresh-token flow once (if `ACLED_REFRESH_TOKEN` is set).
  4. Saves sample response to `outputs/acled_bearer_sample_response.json`.

Token lifetime (from ACLED getting-started docs):
- Access token validity: `24 hours` (`86400` seconds).
- Refresh token validity: `14 days`.

Common auth failures (per ACLED error docs):
- `400`: incorrect username/password (`invalid_grant`).
- `403`: consent not accepted, required profile fields missing, or API access denied.
- `403` with `error code: 1010`: likely edge/WAF block; retry from normal browser network and contact ACLED support if persistent.

Common network/runtime failures:
- `<urlopen error [Errno 8] nodename nor servname provided, or not known>` means hostname resolution failed.
- ACLED read endpoint in this project is `https://acleddata.com/api/acled/read` (not `https://api.acleddata.com/acled/read`).
