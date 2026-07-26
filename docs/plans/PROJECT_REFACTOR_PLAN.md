# Project Refactoring Plan

## Goal

Turn the working news-search repository into a smaller, installable, and easier
to extend product without changing its search behavior. The current
`src/news/` package is a sound foundation; the remaining work is mostly about
runtime resources, configuration, test organization, and boundary cleanup.

This plan uses **refactor** to mean changing code structure without intentionally
changing externally visible behavior.

## Audit Summary

### What is already good

- Reusable Python code is under the `src/news/` package.
- The API, command-line interface, search pipeline, exports, and provider
  adapters have distinct subpackages.
- `pyproject.toml` defines canonical `news-server` and `news-search` commands.
- The test suite is fast and does not require live provider credentials.
- Provider failures are isolated and normalized into source reports.
- The browser uses dependency-free HTML, Cascading Style Sheets (CSS), and
  JavaScript.

### What should change

| Priority | Finding | Why it matters | Planned change |
|---|---|---|---|
| High | Frontend and configuration paths assume a source checkout | An installed wheel cannot reliably find repository-root files | Package static assets and make configuration lookup explicit |
| High | `scripts/acled_oauth_token.py` contains reusable OAuth logic | A script should parse inputs and call package code, not own a full workflow | Move OAuth behavior into `src/news/` and leave a thin wrapper |
| Medium | `tests/test_search_service.py` mixes several domains in one large file | Provider, validation, filtering, and orchestration changes collide | Split tests by the production responsibility they protect |
| Medium | Runtime configuration is returned as untyped dictionaries | Misspelled or invalid values fail late or silently use defaults | Add a typed settings model with validation |
| Medium | API documentation is manually maintained | Route changes can make the reference stale | Generate or contract-test the OpenAPI schema |
| Low | Root guides and the detailed structure reference overlap | Duplicate file maps create documentation drift | Keep conceptual guidance in guides and a compact exact tree in the reference |

## Cleanup Completed on 2026-07-26

- Removed the `notebooks/` provider-exploration tree.
- Removed Jupyter and `nbconvert` from runtime dependencies.
- Removed the exploratory ACLED sample-read script.
- Removed empty `data/`, `logs/`, and pre-created output subfolders.
- Removed completed historical implementation plans that described work already
  present in `src/news/`.
- Stopped writing the raw ACLED OAuth response to disk. Required bearer fields
  are still written to the ignored local `.env`.

Git history remains the recovery path for all removed tracked material.

## Target Structure

```text
.
├── README.md
├── config.toml
├── pyproject.toml
├── uv.lock
├── GUIDE_ROOT.md
├── GUIDE_OVERVIEW.md
├── src/
│   └── news/
│       ├── api/
│       ├── cli/
│       ├── exports/
│       ├── search/
│       ├── sources/
│       └── web/
│           └── static/
├── scripts/
│   └── acled_oauth_token.py
├── tests/
│   ├── api/
│   ├── cli/
│   ├── exports/
│   ├── search/
│   ├── sources/
│   └── web/
└── docs/
    ├── plans/
    ├── reference/
    └── user/
```

Folders should be created only when they contain real files. Generated exports,
caches, credentials, and local environments remain ignored instead of being
represented by tracked `.gitkeep` files.

## Phase 1 -- Make Runtime Resources Installable

**Objective:** make the web application work from an installed package, not
only from this repository checkout.

- [x] Move `frontend/` to `src/news/web/static/`.
- [x] Declare the static files as package data in `pyproject.toml`.
- [x] Replace repository-parent traversal in `news.web.paths` with
  `importlib.resources` for packaged static assets.
- [x] Define an explicit configuration path:
  1. a command-line option when supplied;
  2. a `NEWS_CONFIG` environment variable;
  3. `config.toml` in the current working directory;
  4. packaged defaults.
- [x] Keep `.env` optional and local; document its lookup rather than deriving
  it from the installed module path.
- [x] Add a wheel smoke test that builds the package, installs it into a clean
  temporary environment, starts the application, and requests `/`.

**Acceptance:** `news-server` serves the browser shell from both `uv run` in the
repository and a clean wheel installation.

## Phase 2 -- Type and Validate Configuration

**Objective:** fail early when configuration is invalid.

- [x] Introduce immutable settings types for frontend defaults and cache
  settings.
- [x] Validate source names, positive cache capacity, and positive
  time-to-live values at startup.
- [x] Define every setting once; do not repeat defaults in Python, TOML, and
  JavaScript.
- [x] Pass settings into cache and application construction rather than reading
  global files from low-level modules.
- [x] Add tests for missing config, malformed TOML, unknown sources, and invalid
  numeric values.

**Acceptance:** invalid settings produce one clear startup error, while an
absent optional config uses documented defaults.

## Phase 3 -- Make the ACLED Script Thin

**Objective:** keep reusable provider authentication logic in the package.

- [ ] Move OAuth request, response parsing, and `.env` update logic into a
  focused `news.sources` module.
- [ ] Keep `scripts/acled_oauth_token.py` limited to input loading, calling the
  package function, and terminal messages.
- [ ] Inject the network request function and clock in tests so no live request
  or real credential is required.
- [ ] Test token-key variants, missing fields, Hypertext Transfer Protocol
  (HTTP) errors, and `.env` updates in a temporary directory.
- [ ] Consider a `news-acled-token` entry point only if this remains a regular
  user workflow.

**Acceptance:** the wrapper is small, and all authentication behavior is
covered without network access.

## Phase 4 -- Reorganize Tests by Responsibility

**Objective:** make failures and ownership obvious as the provider set grows.

- [ ] Split validation, filtering, deduplication, and orchestration tests under
  `tests/search/`.
- [ ] Split each provider adapter into its own test module under
  `tests/sources/`.
- [ ] Keep route contract tests under `tests/api/`, command behavior under
  `tests/cli/`, and static-asset checks under `tests/web/`.
- [ ] Add shared response builders under `tests/fixtures/`; avoid a vague
  `utils.py`.
- [ ] Keep live provider checks outside the default suite and mark them
  explicitly if they are added later.

**Acceptance:** each test file maps to one production responsibility, and the
full suite remains offline and deterministic.

## Phase 5 -- Tighten Public Contracts and Documentation

**Objective:** reduce drift between code and user documentation.

- [ ] Decide which Python objects are public and export only those from package
  `__init__.py` files.
- [ ] Add an application factory so tests can supply settings, cache, and fake
  providers without patching module globals.
- [ ] Save the generated OpenAPI schema as a tested contract or generate the
  user API reference from it.
- [ ] Remove file-by-file duplication from `GUIDE_ROOT.md`; keep exact paths in
  `docs/reference/PROJECT_STRUCTURE.md`.
- [ ] Update all guide files in the same commit as each structural phase.

**Acceptance:** API changes cause an intentional contract diff, and each
architectural fact has one authoritative documentation location.

## Execution Rules

For each phase:

1. Add or update tests that define the intended behavior.
2. Make one bounded structural change.
3. Run `uv run ruff check .`.
4. Run `uv run python -m unittest discover -s tests -v`.
5. Build the wheel during Phase 1 and after packaging changes.
6. Update the relevant `GUIDE_*.md` files and structure reference.
7. Commit the phase separately so it can be reviewed or reverted independently.

Do not combine provider features, search-model changes, or frontend redesign
with these refactoring phases. Those are product changes and should have their
own plans.
