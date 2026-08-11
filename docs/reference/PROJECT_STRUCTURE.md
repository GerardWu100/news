# Project Structure

This file records the repository as it exists. Proposed changes belong in
`docs/plans/PROJECT_REFACTOR_PLAN.md`.

## Directory Tree

```text
.
├── .dockerignore
├── .env.example
├── .gitignore
├── .python-version
├── GUIDE_OVERVIEW.md
├── GUIDE_ROOT.md
├── LICENSE
├── README.md
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
├── blog/
│   └── index.md
├── config.toml
├── pyproject.toml
├── uv.lock
├── src/
│   ├── GUIDE_src.md
│   └── news/
│       ├── GUIDE_news.md
│       ├── api/
│       │   ├── app.py
│       │   ├── auth.py
│       │   ├── login_page.py
│       │   ├── models.py
│       │   ├── params.py
│       │   └── trends_params.py
│       ├── cli/
│       │   ├── fetch.py
│       │   ├── output.py
│       │   ├── parser.py
│       │   ├── trends.py
│       │   └── workflow.py
│       ├── exports/
│       │   └── formats.py
│       ├── search/
│       │   ├── cache.py
│       │   ├── deduplication.py
│       │   ├── errors.py
│       │   ├── filters.py
│       │   ├── models.py
│       │   ├── service.py
│       │   └── validation.py
│       ├── trends/
│       │   ├── GUIDE_trends.md
│       │   ├── google.py
│       │   ├── keywords.py
│       │   ├── models.py
│       │   ├── pacing.py
│       │   ├── rebase.py
│       │   └── window.py
│       ├── sources/
│       │   ├── acled_oauth.py
│       │   ├── base.py
│       │   ├── common.py
│       │   ├── registry.py
│       │   ├── retry.py
│       │   └── providers/
│       │       ├── acled.py
│       │       ├── gdelt.py
│       │       ├── guardian.py
│       │       ├── mediacloud.py
│       │       ├── newsapi.py
│       │       └── nyt.py
│       └── web/
│           ├── auth_store.py
│           ├── config.py
│           ├── credentials.py
│           ├── default_config.toml
│           ├── file_locks.py
│           ├── passwords.py
│           ├── paths.py
│           ├── security.py
│           └── static/
│               ├── GUIDE_static.md
│               ├── index.html
│               ├── styles.css
│               └── scripts/
│                   ├── api.js
│                   ├── app.js
│                   ├── form.js
│                   ├── render.js
│                   ├── session.js
│                   └── state.js
├── scripts/
│   ├── GUIDE_scripts.md
│   ├── acled_oauth_token.py
│   └── generate_openapi.py
├── tests/
│   ├── GUIDE_tests.md
│   ├── test_docker_setup.py
│   ├── api/
│   │   ├── test_app.py
│   │   ├── test_auth.py
│   │   ├── test_config.py
│   │   ├── test_openapi_contract.py
│   │   ├── test_public_exports.py
│   │   ├── test_server_cli.py
│   │   └── test_trends_endpoint.py
│   ├── cli/
│   │   ├── test_cli.py
│   │   ├── test_cli_authentication.py
│   │   └── test_trends_cli.py
│   ├── exports/
│   │   └── test_formats.py
│   ├── fixtures/
│   │   ├── authentication.py
│   │   ├── search_results.py
│   │   └── trends_results.py
│   ├── search/
│   │   ├── test_cache.py
│   │   ├── test_deduplication.py
│   │   ├── test_filters.py
│   │   ├── test_service.py
│   │   └── test_validation.py
│   ├── trends/
│   │   ├── test_google.py
│   │   ├── test_keywords.py
│   │   ├── test_pacing.py
│   │   └── test_rebase.py
│   ├── sources/
│   │   ├── test_acled_oauth.py
│   │   ├── test_retry.py
│   │   └── providers/
│   │       ├── test_acled.py
│   │       ├── test_article_date_contract.py
│   │       ├── test_gdelt.py
│   │       ├── test_guardian.py
│   │       ├── test_mediacloud.py
│   │       ├── test_newsapi.py
│   │       └── test_nyt.py
│   └── web/
│       ├── test_credentials.py
│       ├── test_passwords.py
│       ├── test_static.py
│       └── test_wheel_installation.py
└── docs/
    ├── plans/
    │   └── PROJECT_REFACTOR_PLAN.md
    ├── reference/
    │   ├── PROJECT_STRUCTURE.md
    │   └── openapi.json
    └── user/
        ├── API_REFERENCE.md
        ├── DOCKER.md
        └── SIGN_IN.md
```

Package marker files named `__init__.py` are omitted from the tree for
readability.

## Responsibility Map

| Path | Responsibility |
|---|---|
| `src/news/api/` | Hypertext Transfer Protocol (HTTP) routes, request parsing, response models, sign-in routes, and the check that closes every data route |
| `src/news/cli/` | Command parsing, fetch modes, terminal output, and exports |
| `src/news/exports/` | CSV, JSON, and SQLite serialization |
| `src/news/search/` | Validated search behavior, cache, filters, duplicate removal, and search details |
| `src/news/sources/` | Source access, ACLED OAuth setup, retries and pauses, registry, and parallel requests |
| `src/news/trends/` | Google Trends retrieval for one explicit past window, query-to-keyword conversion, request spacing, and as-of rescaling |
| `src/news/web/` | Typed configuration validation, package defaults, path lookup, password hashing, stored sign-in state, and installed browser assets |
| `blog/` | Local-only article source about the deployment and agent workflow |
| `scripts/` | Thin ACLED credential and OpenAPI generation commands |
| `tests/` | Deterministic offline regression coverage |
| `docs/plans/` | Forward-looking work that has not necessarily been implemented |
| `docs/reference/` | Developer ground truth for the implemented system |
| `docs/user/` | User-facing documentation |
| Root Docker files | Image build, Compose runtime, persistent configuration seeding, and build-context exclusions |

## Important Root Files

- `config.toml`: documented browser, cache, and proxy-trust settings.
- `pyproject.toml`: dependencies, package discovery, and executable commands.
- `README.md`: setup, normal commands, and documentation links.
- `.env.example`: secret-free sign-in account and provider credential template.
- `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, and
  `.dockerignore`: self-hosted deployment boundary.
- `GUIDE_OVERVIEW.md`: conceptual system flow and constraints.
- `GUIDE_ROOT.md`: developer navigation from the repository root.
