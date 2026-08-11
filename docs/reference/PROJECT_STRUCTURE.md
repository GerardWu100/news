# Project Structure

This file describes the repository as it exists. Proposed changes belong in
`docs/plans/PROJECT_REFACTOR_PLAN.md`.

## Directory tree

```text
.
├── .agents/skills/news-cli/       AI-agent retrieval instructions
├── .dockerignore                  Docker build exclusions
├── .env.example                   account and provider-key template
├── GUIDE_OVERVIEW.md              system overview
├── GUIDE_ROOT.md                  root navigation
├── Dockerfile                     image definition
├── docker-compose.yml             container runtime
├── docker-entrypoint.sh           container startup
├── blog/index.md                  local article source
├── config.toml                    local settings
├── pyproject.toml                dependencies and commands
├── src/
│   ├── GUIDE_src.md
│   └── news/
│       ├── GUIDE_news.md
│       ├── api/                   web routes and sign-in
│       ├── cli/                   command-line workflows
│       ├── exports/               CSV, JSON, and SQLite writers
│       ├── search/                validation and result handling
│       ├── sources/               provider adapters
│       ├── trends/                Google Trends retrieval
│       └── web/                   settings, auth state, and browser assets
├── scripts/                       small credential/schema commands
├── tests/                         offline regression tests
└── docs/
    ├── plans/                     proposed work
    ├── reference/                 schema and this file
    └── user/                      API, Docker, and sign-in guides
```

Package marker files named `__init__.py` are omitted. See the repository tree
for the complete file list.

## Responsibility map

| Path | Responsibility |
|---|---|
| `src/news/api/` | HTTP routes, request parsing, response models, and sign-in checks |
| `src/news/cli/` | command parsing, retrieval modes, terminal output, and exports |
| `src/news/exports/` | CSV, JSON, and SQLite serialization |
| `src/news/search/` | validation, cache, filters, deduplication, sorting, and search details |
| `src/news/sources/` | provider access, ACLED login, retries, settings, and parallel requests |
| `src/news/trends/` | historical Google Trends data, keyword conversion, pacing, and as-of rescaling |
| `src/news/web/` | settings validation, paths, password hashing, sign-in state, and packaged browser files |
| `.agents/skills/news-cli/` | retrieval and coverage checks for an outside AI agent |
| `blog/` | local-only article source |
| `scripts/` | ACLED credential refresh and OpenAPI generation |
| `tests/` | deterministic offline regression coverage |
| `docs/plans/` | work that is not necessarily implemented |
| `docs/reference/` | developer reference for the implemented system |
| `docs/user/` | user-facing documentation |
| Root Docker files | image build, Compose runtime, persistent settings, and build exclusions |

## Important root files

- `config.toml`: browser, cache, proxy, Trends, and provider-request settings.
- `pyproject.toml`: dependencies, package discovery, and executable commands.
- `README.md`: setup, normal commands, and links to deeper documentation.
- `.env.example`: secret-free account and provider-key template.
- `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, and
  `.dockerignore`: the self-hosted deployment boundary.
- `GUIDE_OVERVIEW.md`: conceptual system flow and constraints.
- `GUIDE_ROOT.md`: navigation from the repository root.
