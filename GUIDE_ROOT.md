# GUIDE_ROOT

## Part 1 -- Conceptual Explanation

### Purpose

The project root coordinates an installable historical news-retrieval product.
The Python package owns the API, command-line interface (CLI), provider
adapters, search pipeline, exports, validated settings, and static browser
assets. Root files configure development, document usage, and provide local
operator overrides.

### Runtime flow

1. `news-server` resolves optional credentials, validated configuration, and
   configurable bind settings.
2. The application factory builds an isolated process cache and binds provider
   execution and status dependencies.
3. Browser or CLI inputs become one validated search request.
4. Requested providers execute concurrently and normalize their records.
5. Local filtering, conservative deduplication, and stable sorting produce one
   provider page.
6. The API returns JavaScript Object Notation (JSON); the CLI can also write
   comma-separated values (CSV), JSON, or SQLite.

### Runtime and generated state

- `.env` in the process working directory holds optional provider credentials
  plus the optional `NEWS_SERVER_URL` CLI default and is never tracked.
- External TOML overrides packaged defaults through `--config`, `NEWS_CONFIG`,
  or current-directory `config.toml`, in that order.
- Docker seeds the repository defaults into the mounted
  `${HOME}/.containers/news` data directory once, then preserves operator
  changes across image rebuilds.
- Exports, environments, caches, logs, and build artifacts are generated only
  when needed and remain ignored.
- The checked-in OpenAPI schema is generated from the application and tested as
  the public HTTP contract.

The exact implemented tree and responsibility table live only in
`docs/reference/PROJECT_STRUCTURE.md`. The high-level system view is in
`GUIDE_OVERVIEW.md`.

## Part 2 -- Code Reference

- `README.md`: user setup, canonical commands, and documentation entry points.
- `pyproject.toml`: dependencies, package discovery, package data, and commands.
- `config.toml`: documented local frontend and cache overrides.
- `.env.example`: secret-free provider credential template.
- `Dockerfile`, `docker-compose.yml`, and `docker-entrypoint.sh`: self-hosted
  image, deployment defaults, persistent configuration seeding, and a
  Dockerized CLI client.
- `.dockerignore`: excludes development, secret, test, documentation, and local
  artifact files from the image build context.
- `.agents/skills/summarize-news-cli/`: workspace-only agent procedure for
  CLI retrieval and evidence-bounded news summaries.
- `blog/`: local article source; it is not a website publish target.
- `src/`: importable implementation and installed resources; start with
  `src/GUIDE_src.md`.
- `scripts/`: thin local workflow commands; see `scripts/GUIDE_scripts.md`.
- `tests/`: deterministic tests organized by production responsibility; see
  `tests/GUIDE_tests.md`.
- `docs/user/`: user-facing API documentation.
- `docs/reference/`: exact developer structure and generated OpenAPI contract.
- `docs/plans/`: implementation plans, whose checkboxes distinguish completed
  and outstanding work.

## Part 3 -- Short Journal

- 2026-07-26: Removed obsolete research artifacts and kept Git history as their recovery path.
- 2026-07-26: Packaged browser assets and defaults so installed wheels do not depend on repository-parent traversal.
- 2026-07-26: Replaced permissive configuration dictionaries with immutable validated settings and explicit cache injection.
- 2026-07-26: Made package exports, application dependencies, and the generated OpenAPI schema explicit contracts.
- 2026-07-26: Kept API module imports free of configuration reads so `news-server --config` is resolved before application construction.
- 2026-07-29: Mirrored the podcast-downloader Docker operations pattern while keeping the unauthenticated API loopback-only and reserving host port 50023.
- 2026-07-29: Made remote agent endpoints configurable through `NEWS_SERVER_URL` and kept the summary skill local to this workspace.
- 2026-08-08: Moved lint rules into `pyproject.toml` so import order and modern-syntax rewrites are decided by ruff instead of by hand.
- 2026-08-08: Gave `Article` one accessor for its provenance so the "no recorded sources means the originating source" rule is interpreted in a single place.
- 2026-08-08: Made every browser render function announce its own outcome, because pairing announcements with render calls by hand had already left two error paths silent.
- 2026-08-09: Added Google Trends retrieval (`news-trends`, `/api/trends/*`) as its own package behind a replaceable client interface, because the archived `pytrends` library scrapes unofficial endpoints and may need swapping without touching callers.
