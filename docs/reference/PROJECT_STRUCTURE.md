# Project Structure

This file records the repository as it exists. Proposed changes belong in
`docs/plans/PROJECT_REFACTOR_PLAN.md`.

## Directory Tree

```text
.
├── .agents/
│   └── skills/
│       └── summarize-news-cli/
│           ├── SKILL.md
│           └── agents/openai.yaml
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
│       │   ├── models.py
│       │   └── params.py
│       ├── cli/
│       │   ├── fetch.py
│       │   ├── output.py
│       │   ├── parser.py
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
│           ├── config.py
│           ├── default_config.toml
│           ├── paths.py
│           └── static/
│               ├── GUIDE_static.md
│               ├── index.html
│               ├── styles.css
│               └── scripts/
│                   ├── api.js
│                   ├── app.js
│                   ├── form.js
│                   ├── render.js
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
│   │   ├── test_config.py
│   │   ├── test_openapi_contract.py
│   │   ├── test_public_exports.py
│   │   └── test_server_cli.py
│   ├── cli/
│   │   └── test_cli.py
│   ├── exports/
│   │   └── test_formats.py
│   ├── fixtures/
│   │   └── search_results.py
│   ├── search/
│   │   ├── test_cache.py
│   │   ├── test_deduplication.py
│   │   ├── test_filters.py
│   │   ├── test_service.py
│   │   └── test_validation.py
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
        └── DOCKER.md
```

Package marker files named `__init__.py` are omitted from the tree for
readability.

## Responsibility Map

| Path | Responsibility |
|---|---|
| `src/news/api/` | Hypertext Transfer Protocol (HTTP) routes, request parsing, and response models |
| `src/news/cli/` | Command parsing, fetch modes, terminal output, and exports |
| `src/news/exports/` | CSV, JSON, and SQLite serialization |
| `src/news/search/` | Validated search behavior, cache, filters, duplicate removal, and search details |
| `src/news/sources/` | Source access, ACLED OAuth setup, retries and pauses, registry, and parallel requests |
| `src/news/web/` | Typed configuration validation, package defaults, path lookup, and installed browser assets |
| `.agents/skills/summarize-news-cli/` | Workspace-local AI-agent retrieval, coverage audit, and summary procedure |
| `blog/` | Local-only article source about the deployment and agent workflow |
| `scripts/` | Thin ACLED credential and OpenAPI generation commands |
| `tests/` | Deterministic offline regression coverage |
| `docs/plans/` | Forward-looking work that has not necessarily been implemented |
| `docs/reference/` | Developer ground truth for the implemented system |
| `docs/user/` | User-facing documentation |
| Root Docker files | Image build, Compose runtime, persistent configuration seeding, and build-context exclusions |

## Important Root Files

- `config.toml`: documented browser and cache settings.
- `pyproject.toml`: dependencies, package discovery, and executable commands.
- `README.md`: setup, normal commands, and documentation links.
- `.env.example`: secret-free provider credential template.
- `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, and
  `.dockerignore`: self-hosted deployment boundary.
- `GUIDE_OVERVIEW.md`: conceptual system flow and constraints.
- `GUIDE_ROOT.md`: developer navigation from the repository root.
