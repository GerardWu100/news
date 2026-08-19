# GUIDE_ROOT

## What the root contains

This repository is the installable Historical Market News Search service. The
Python package owns the API, CLI, provider adapters, search rules, Google
Trends retrieval, exports, settings, and browser files. Root files cover
configuration, deployment, tests, and documentation.

## Runtime flow

1. `news-server` reads the account, settings, and bind options.
2. The application creates its cache and opens the stored sign-in state.
3. A browser uses a session cookie. The CLI sends the same account in an HTTP
   Basic header. Data routes reject unauthenticated requests.
4. Browser or CLI input becomes one validated search request.
5. Selected providers run in parallel. Their records are normalized, filtered,
   optionally deduplicated, sorted, and returned as one page.
6. The API returns JSON. The CLI also supports CSV, JSON, JSON Lines, and
   SQLite.
7. `news-trends` runs separately: it sends the query and dates directly to
   Google Trends and does not contact the server.

## Runtime and generated files

- `NEWS_DATA_DIR` chooses the data directory. Without it, the process uses its
  working directory; Docker maps it to `/data`.
- `.env` stores accounts, provider credentials, and the optional CLI server
  address. It is never tracked.
- `.ui_credentials.json`, `.ui_sessions.json`, `.login_state.json`, and
  `.login_form_tokens.json` store password hashes, active sessions,
  failed-attempt counters, and short-lived one-time sign-in tokens. They are
  owner-only and updated under file locks so several workers can share them.
- Settings come from `--config`, `NEWS_CONFIG`, `config.toml`, or packaged
  defaults, in that order.
- Docker seeds defaults into `${HOME}/.containers/news` once and preserves
  operator changes across image rebuilds.
- Exports, caches, logs, environments, and build files are created only when
  needed and are ignored by Git.
- The checked-in OpenAPI schema is generated from the application and tested as
  the public HTTP contract.

See `docs/reference/PROJECT_STRUCTURE.md` for the exact tree and
`GUIDE_OVERVIEW.md` for the system-level explanation.

## Root file map

- `README.md`: setup and everyday commands.
- `pyproject.toml`: dependencies, package discovery, and the three commands.
- `config.toml`: browser, cache, proxy, Trends, and provider settings.
- `.env.example`: account and provider-credential template.
- `Dockerfile`, `docker-compose.yml`, and `docker-entrypoint.sh`: container
  build and runtime behavior.
- `.agents/skills/news-cli/`: retrieval and coverage instructions for an
  outside AI agent.
- `blog/`: local article source, not a publishing target.
- `src/`: installed implementation; start with `src/GUIDE_src.md`.
- `scripts/`: small local commands; see `scripts/GUIDE_scripts.md`.
- `tests/`: offline tests by production responsibility.
- `docs/user/`: user-facing API, Docker, and sign-in documentation.
- `docs/reference/`: project structure and generated OpenAPI definition.
- `docs/plans/`: proposed work, not necessarily implemented.

## Short journal

- 2026-08-19: Moved one-time sign-in tokens and credential startup changes behind cross-process locks, and stopped public static routes from exposing guarded HTML files.
- 2026-08-19: Made multi-page exports preserve page-level failures and deduplicate across page boundaries.
- 2026-08-12: Renamed the product to Historical Market News Search so its market scope and search function are explicit.
- 2026-07-26: Packaged browser assets and defaults so installed wheels do not need the repository root.
- 2026-07-26: Replaced loose configuration dictionaries with validated settings and explicit cache passing.
- 2026-07-26: Made package exports, application dependencies, and the OpenAPI schema explicit.
- 2026-07-29: Kept the Docker API on loopback and made remote agent addresses configurable.
- 2026-08-08: Moved lint rules into `pyproject.toml` and centralized `Article` source history.
- 2026-08-08: Made browser display functions announce their results for screen readers.
- 2026-08-10: Made startup derive stored password hashes from `.env` accounts, and moved sessions behind a shared file lock.
- 2026-08-10: Centralized browser security headers, removed secrets from logged provider errors, and restricted trusted forwarded addresses.
- 2026-08-10: Used the same account for CLI HTTP Basic authentication and left `WWW-Authenticate` off 401 responses.
- 2026-08-11: Changed the Docker host port to 50024 and hardened the container without creating a new account.
- 2026-08-11: Replaced the bundled summary skill with retrieval-only instructions for outside agents.
