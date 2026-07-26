# GUIDE_ROOT

## Part 1 -- Conceptual Explanation

### Purpose

The project root coordinates an installable historical news-retrieval product.
The Python package owns the API, command-line interface (CLI), provider
adapters, search pipeline, exports, validated settings, and static browser
assets. Root files configure development, document usage, and provide local
operator overrides.

### Runtime flow

1. `news-server` resolves optional credentials and validated configuration.
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
  and is never tracked.
- External TOML overrides packaged defaults through `--config`, `NEWS_CONFIG`,
  or current-directory `config.toml`, in that order.
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
