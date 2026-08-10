# GUIDE_ROOT

## Part 1 -- What the root contains

The repository root ties together an installable historical news-retrieval
product. The Python package owns the API, CLI, source adapters, search rules,
exports, validated settings, and browser files. Root files hold development
configuration, user documentation, and local operator settings.

### Runtime flow

1. `news-server` reads credentials, settings, and bind options, then hashes the
   sign-in password and verifies the stored hash.
2. The application factory creates a local cache, opens the stored sign-in
   state, and connects the source request and status functions.
3. A browser signs in through a form and keeps a session cookie; the CLI sends
   the same account as an HTTP Basic header. Data routes refuse everything
   else.
4. Browser or CLI input becomes one validated search request.
5. Selected sources are queried in parallel and their records are normalized.
6. Local filtering, cautious duplicate removal, and stable sorting produce one
   source page.
7. The API returns JSON; the CLI can also write CSV, JSON, or SQLite.

### Runtime files and generated files

- The data directory is `NEWS_DATA_DIR` when set and the process working
  directory otherwise. Docker points it at the mounted `/data`.
- `.env` in the data directory holds the sign-in account, provider credentials,
  and the optional `NEWS_SERVER_URL` CLI default. It is never tracked.
- `.ui_credentials.json`, `.ui_sessions.json`, and `.login_state.json` in the
  data directory hold the hashed password, remembered browsers, and
  failed-attempt counters. All three are owner-only and never tracked. The two
  state files are read and written under a lock on every use, so several server
  processes can serve one data directory.
- External TOML settings override packaged defaults through `--config`,
  `NEWS_CONFIG`, or `config.toml` in the current directory, in that order.
- Docker seeds the repository defaults into `${HOME}/.containers/news` once and
  keeps operator changes across image rebuilds.
- Exports, environments, caches, logs, and build files are created only when
  needed and remain ignored.
- The checked-in OpenAPI schema is generated from the application and tested as
  the public HTTP definition.

The exact tree and responsibility table are in
`docs/reference/PROJECT_STRUCTURE.md`. The system-level explanation is in
`GUIDE_OVERVIEW.md`.

## Part 2 -- Code reference

- `README.md`: setup, normal commands, and documentation links.
- `pyproject.toml`: dependencies, package discovery, package data, and commands.
- `config.toml`: local browser, cache, and proxy-trust settings.
- `.env.example`: secret-free sign-in account and credential template.
- `Dockerfile`, `docker-compose.yml`, and `docker-entrypoint.sh`: self-hosted
  image, deployment defaults, persistent settings, and Dockerized CLI use.
- `.dockerignore`: files excluded from the image build context.
- `.agents/skills/summarize-news-cli/`: workspace-only agent procedure for
  retrieval and evidence-bounded summaries.
- `blog/`: local article source; it is not a website publish target.
- `src/`: importable implementation and installed resources; start with
  `src/GUIDE_src.md`.
- `scripts/`: small local commands; see `scripts/GUIDE_scripts.md`.
- `tests/`: deterministic tests by production responsibility; see
  `tests/GUIDE_tests.md`.
- `docs/user/`: user-facing API, Docker, and sign-in documentation.
- `docs/reference/`: exact structure and generated OpenAPI definition.
- `docs/plans/`: plans, with checkboxes for completed and outstanding work.

## Part 3 -- Short journal

- 2026-07-26: Removed obsolete research files and kept Git history as their recovery path.
- 2026-07-26: Packaged browser assets and defaults so an installed wheel does not need to search above the package directory.
- 2026-07-26: Replaced loose configuration dictionaries with validated settings and passed the cache explicitly.
- 2026-07-26: Made package exports, application dependencies, and the generated OpenAPI schema explicit public definitions.
- 2026-07-26: Kept API imports free of configuration reads so `news-server --config` is resolved before the application is built.
- 2026-07-29: Followed the Docker operations pattern used by the podcast downloader while keeping the unauthenticated API on loopback and reserving port 50023.
- 2026-07-29: Made remote agent addresses configurable through `NEWS_SERVER_URL` and kept the summary skill local to this workspace.
- 2026-08-08: Moved lint rules into `pyproject.toml` so ruff, rather than manual judgment, decides import order and modern-syntax rewrites.
- 2026-08-08: Gave `Article` one accessor for source history so its fallback rule is applied in one place.
- 2026-08-08: Made every browser display function announce its result because two error paths had previously stayed silent.
- 2026-08-10: Adopted the podcast downloader's sign-in model, so the operator sets a plain account in `.env` and startup, not a separate command, produces the stored hash.
- 2026-08-10: Moved session state out of process memory and behind the file lock, because the in-memory copy meant a browser signed in through one worker was refused by the next.
- 2026-08-10: Attached browser protection headers in one middleware instead of route by route, after the search page turned out to be serving third-party article text with no Content Security Policy.
- 2026-08-10: Made the container serve as an unprivileged account with a read-only root filesystem, which requires the operator to set `NEWS_UID` and `NEWS_GID` to own the mounted data directory.
- 2026-08-10: Stopped logging source exceptions verbatim, because the request address in an HTTP error carries the provider key that travels in the query string.
- 2026-08-10: Required the direct peer to be local or private before believing `X-Forwarded-For`, so the setting alone can no longer be used to bypass the failed-attempt limit.
- 2026-08-10: Gave the command line HTTP Basic against the same account rather than a second token, because one secret is easier to rotate than two and the CLI already reads `.env`.
- 2026-08-10: Left `WWW-Authenticate` off the 401 responses so the browser shows this application's sign-in page instead of its own native password box.
