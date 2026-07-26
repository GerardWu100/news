# Product Package Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the project to a `src/news/` product package while preserving search, API, CLI, frontend, and export capabilities.

**Architecture:** Product Python code moves from the broad `backend/` package into `src/news/` subpackages organized by responsibility: `api`, `search`, `sources`, `cli`, `exports`, and `web`. Old root compatibility files are removed because the approved design preserves product behavior, not old paths.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, HTTPX, python-dotenv, unittest, Ruff, uv.

---

## File Structure

Create or modify these product files:

- Create: `src/GUIDE_src.md`
- Create: `src/news/GUIDE_news.md`
- Create: `src/news/__init__.py`
- Create: `src/news/api/__init__.py`
- Move and modify: `backend/app.py` -> `src/news/api/app.py`
- Move and modify: `backend/api_models.py` -> `src/news/api/models.py`
- Create: `src/news/api/params.py`
- Move and modify: `backend/cli/` -> `src/news/cli/`
- Move and modify: `backend/export.py` -> `src/news/exports/formats.py`
- Create: `src/news/exports/__init__.py`
- Move and modify: `backend/search/` -> `src/news/search/`
- Move and modify: `backend/sources/base.py` -> `src/news/sources/base.py`
- Move and modify: `backend/sources/common.py` -> `src/news/sources/common.py`
- Move and modify: `backend/sources/registry.py` -> `src/news/sources/registry.py`
- Move and modify: `backend/sources/retry.py` -> `src/news/sources/retry.py`
- Move and modify: `backend/sources/__init__.py` -> `src/news/sources/__init__.py`
- Create: `src/news/sources/providers/__init__.py`
- Move and modify provider adapters from `backend/sources/*.py` into `src/news/sources/providers/`
- Create: `src/news/web/__init__.py`
- Create: `src/news/web/config.py`
- Create: `src/news/web/paths.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `GUIDE_ROOT.md`
- Modify: `PROJECT_STRUCTURE.md`
- Modify: `tests/GUIDE_tests.md`
- Modify: all tests that import `backend...`
- Delete: `backend/`
- Delete: `main.py`
- Delete: `cli.py`
- Delete or replace: `backend/GUIDE_backend.md` and `backend/cli/GUIDE_cli.md`

---

### Task 1: Add New Package Expectations To Tests

**Files:**
- Modify: `tests/test_app.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_export.py`
- Modify: `tests/test_cache.py`
- Modify: `tests/test_retry.py`
- Modify: `tests/test_search_service.py`

- [ ] **Step 1: Update imports from `backend...` to `news...`**

Use these import mapping rules:

```text
backend.app -> news.api.app
backend.api_models -> news.api.models
backend.export -> news.exports.formats
backend.cli -> news.cli
backend.search -> news.search
backend.sources -> news.sources
backend.sources.acled -> news.sources.providers.acled
backend.sources.gdelt -> news.sources.providers.gdelt
backend.sources.guardian -> news.sources.providers.guardian
backend.sources.mediacloud -> news.sources.providers.mediacloud
backend.sources.newsapi -> news.sources.providers.newsapi
backend.sources.nyt -> news.sources.providers.nyt
```

Run:

```bash
perl -pi -e 's/from backend\.app/from news.api.app/g; s/import backend\.app/import news.api.app/g' tests/*.py
perl -pi -e 's/from backend\.export/from news.exports.formats/g' tests/*.py
perl -pi -e 's/from backend\.cli/from news.cli/g' tests/*.py
perl -pi -e 's/from backend\.search/from news.search/g' tests/*.py
perl -pi -e 's/from backend\.sources\.acled/from news.sources.providers.acled/g' tests/*.py
perl -pi -e 's/from backend\.sources\.gdelt/from news.sources.providers.gdelt/g' tests/*.py
perl -pi -e 's/from backend\.sources\.guardian/from news.sources.providers.guardian/g' tests/*.py
perl -pi -e 's/from backend\.sources\.mediacloud/from news.sources.providers.mediacloud/g' tests/*.py
perl -pi -e 's/from backend\.sources\.newsapi/from news.sources.providers.newsapi/g' tests/*.py
perl -pi -e 's/from backend\.sources\.nyt/from news.sources.providers.nyt/g' tests/*.py
perl -pi -e 's/from backend\.sources/from news.sources/g' tests/*.py
```

- [ ] **Step 2: Update FastAPI patch targets**

In `tests/test_app.py`, replace every patch target:

```python
patch("backend.app.run_search", new=AsyncMock(return_value=FAKE_RESULT))
```

with:

```python
patch("news.api.app.run_search", new=AsyncMock(return_value=FAKE_RESULT))
```

- [ ] **Step 3: Remove old root CLI compatibility test**

In `tests/test_cli.py`, delete the whole `RootCliCompatibilityTests` class because
`cli.py` compatibility is no longer required.

- [ ] **Step 4: Add package script metadata tests**

Append this test class to `tests/test_cli.py` before the `if __name__ == "__main__"` block:

```python
class PackageEntryPointTests(unittest.TestCase):
    """Check that package entry points are available through project metadata."""

    def test_pyproject_defines_news_scripts(self) -> None:
        """The project should expose canonical server and CLI commands."""
        import tomllib
        from pathlib import Path

        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        scripts = pyproject["project"]["scripts"]

        self.assertEqual(scripts["news-server"], "news.api.app:main")
        self.assertEqual(scripts["news-search"], "news.cli.workflow:main")
```

- [ ] **Step 5: Run the targeted tests and confirm they fail for the expected reason**

Run:

```bash
uv run python -m unittest tests.test_app tests.test_cli tests.test_export tests.test_cache tests.test_retry tests.test_search_service -v
```

Expected: fail with `ModuleNotFoundError: No module named 'news'` or missing `project.scripts`.

- [ ] **Step 6: Commit the failing package expectation tests**

```bash
git add tests
git commit -m "test: expect news package structure"
```

---

### Task 2: Move Product Code Into `src/news`

**Files:**
- Create: `src/news/`
- Move: `backend/search/` -> `src/news/search/`
- Move: `backend/cli/` -> `src/news/cli/`
- Move: `backend/app.py` -> `src/news/api/app.py`
- Move: `backend/api_models.py` -> `src/news/api/models.py`
- Move: `backend/export.py` -> `src/news/exports/formats.py`
- Move: `backend/sources/` files into `src/news/sources/`
- Delete: `backend/`

- [ ] **Step 1: Create destination folders**

Run:

```bash
mkdir -p src/news/api src/news/exports src/news/sources/providers src/news/web
```

- [ ] **Step 2: Move existing modules**

Run:

```bash
git mv backend/search src/news/search
git mv backend/cli src/news/cli
git mv backend/app.py src/news/api/app.py
git mv backend/api_models.py src/news/api/models.py
git mv backend/export.py src/news/exports/formats.py
git mv backend/sources/__init__.py src/news/sources/__init__.py
git mv backend/sources/base.py src/news/sources/base.py
git mv backend/sources/common.py src/news/sources/common.py
git mv backend/sources/registry.py src/news/sources/registry.py
git mv backend/sources/retry.py src/news/sources/retry.py
git mv backend/sources/acled.py src/news/sources/providers/acled.py
git mv backend/sources/gdelt.py src/news/sources/providers/gdelt.py
git mv backend/sources/guardian.py src/news/sources/providers/guardian.py
git mv backend/sources/mediacloud.py src/news/sources/providers/mediacloud.py
git mv backend/sources/newsapi.py src/news/sources/providers/newsapi.py
git mv backend/sources/nyt.py src/news/sources/providers/nyt.py
git rm backend/__init__.py backend/GUIDE_backend.md src/news/cli/GUIDE_cli.md
rmdir backend
```

- [ ] **Step 3: Create new package marker files**

Create `src/news/__init__.py`:

```python
"""Historical multi-source news retrieval package."""
```

Create `src/news/api/__init__.py`:

```python
"""HTTP API boundary for the news retrieval package."""
```

Create `src/news/exports/__init__.py`:

```python
"""Export format helpers for normalized news search results."""
```

Create `src/news/sources/providers/__init__.py`:

```python
"""Provider-specific source adapters."""
```

Create `src/news/web/__init__.py`:

```python
"""Project path and configuration helpers for runtime boundaries."""
```

- [ ] **Step 4: Run tests and confirm import failures are now narrower**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected: fail with import errors inside moved modules because internal imports
still reference `backend` or old provider locations.

- [ ] **Step 5: Commit the mechanical move**

```bash
git add src tests
git add -u
git commit -m "refactor: move product code into src news package"
```

---

### Task 3: Fix Internal Imports After The Move

**Files:**
- Modify: `src/news/api/app.py`
- Modify: `src/news/cli/fetch.py`
- Modify: `src/news/cli/output.py`
- Modify: `src/news/cli/workflow.py`
- Modify: `src/news/search/service.py`
- Modify: `src/news/sources/registry.py`
- Modify: all files in `src/news/sources/providers/`

- [ ] **Step 1: Replace absolute backend imports in product code**

Run:

```bash
rg -l "backend\.export|backend\.search|backend\.sources|import backend" src/news | xargs perl -pi -e 's/from backend\.export/from news.exports.formats/g; s/from backend\.search/from news.search/g; s/from backend\.sources/from news.sources/g; s/import backend/import news/g'
```

- [ ] **Step 2: Fix API imports**

In `src/news/api/app.py`, the imports should include:

```python
from news.exports.formats import format_csv, format_json
from news.api.models import (
    FrontendConfigResponse,
    SearchResponse,
    SourceStatusResponse,
)
from news.search import build_search_request, run_search
from news.search.errors import SearchValidationError
from news.search.models import SearchRequest
from news.sources import get_source_status
```

- [ ] **Step 3: Fix CLI imports**

In `src/news/cli/fetch.py`, replace the direct-mode import inside
`fetch_direct_page` with:

```python
from news.search import build_search_request, run_search
```

In `src/news/cli/output.py`, ensure export imports are:

```python
from news.exports.formats import format_csv, format_json, write_sqlite
```

In `src/news/cli/workflow.py`, ensure validation import is:

```python
from news.search.errors import SearchValidationError
```

- [ ] **Step 4: Fix provider registry imports**

In `src/news/sources/registry.py`, use provider subpackage imports:

```python
from news.sources.providers.acled import AcledSource
from news.sources.base import BaseSource
from news.sources.providers.gdelt import GdeltSource
from news.sources.providers.guardian import GuardianSource
from news.sources.providers.mediacloud import MediaCloudSource
from news.sources.providers.newsapi import NewsApiSource
from news.sources.providers.nyt import NewYorkTimesSource
```

- [ ] **Step 5: Fix provider relative imports**

In each file under `src/news/sources/providers/`, replace same-package imports
for shared source modules:

```text
from .base -> from news.sources.base
from .common -> from news.sources.common
from .retry -> from news.sources.retry
```

Run:

```bash
perl -pi -e 's/from \.base/from news.sources.base/g' src/news/sources/providers/*.py
perl -pi -e 's/from \.common/from news.sources.common/g' src/news/sources/providers/*.py
perl -pi -e 's/from \.retry/from news.sources.retry/g' src/news/sources/providers/*.py
```

- [ ] **Step 6: Run import scan**

Run:

```bash
rg -n "backend\.|from backend|import backend|sources\.(acled|gdelt|guardian|mediacloud|newsapi|nyt)" src tests
```

Expected: no output.

- [ ] **Step 7: Run tests**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected: remaining failures should be about app paths, missing scripts, or old
root files, not `backend` imports.

- [ ] **Step 8: Commit import fixes**

```bash
git add src tests
git commit -m "refactor: update imports for news package"
```

---

### Task 4: Add Runtime Path And Config Helpers

**Files:**
- Create: `src/news/web/paths.py`
- Create: `src/news/web/config.py`
- Modify: `src/news/api/app.py`
- Modify: `src/news/cli/fetch.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Add `src/news/web/paths.py`**

```python
"""Path helpers for project-level runtime resources.

The package lives under ``src/news`` while runtime resources such as
``config.toml``, ``.env``, and ``frontend/`` live at the project root. This
module centralizes that relationship so API and CLI modules do not duplicate
fragile parent-directory arithmetic.
"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root for a source checkout.

    Returns
    -------
    Path
        Absolute path to the project root directory.
    """
    return Path(__file__).resolve().parents[3]


def env_path() -> Path:
    """Return the project-root dotenv file path."""
    return project_root() / ".env"


def config_path() -> Path:
    """Return the project-root TOML configuration path."""
    return project_root() / "config.toml"


def frontend_dir() -> Path:
    """Return the static frontend asset directory."""
    return project_root() / "frontend"
```

- [ ] **Step 2: Add `src/news/web/config.py`**

```python
"""Configuration loading helpers for runtime boundaries."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from news.web.paths import config_path


def read_config(path: Path | None = None) -> dict[str, Any]:
    """Read a TOML configuration file.

    Parameters
    ----------
    path : Path | None, optional
        Configuration file path. ``None`` uses the project-root
        ``config.toml``.

    Returns
    -------
    dict[str, Any]
        Parsed TOML mapping. Missing config files return an empty mapping.
    """
    active_path = config_path() if path is None else path
    if not active_path.exists():
        return {}

    with active_path.open("rb") as config_file:
        return tomllib.load(config_file)


def read_frontend_config(path: Path | None = None) -> dict[str, Any]:
    """Return the frontend table from the project configuration."""
    config = read_config(path)
    return config.get("frontend", {})
```

- [ ] **Step 3: Update `src/news/api/app.py` to use helpers**

Replace local `_ENV_PATH`, `_CONFIG_PATH`, `_FRONTEND_DIR`, and `_read_config`
logic with:

```python
from news.web.config import read_frontend_config
from news.web.paths import env_path, frontend_dir

load_dotenv(env_path())
FRONTEND_DIR = frontend_dir()
```

Update the static mount and index route:

```python
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    """Serve the browser app."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))
```

Update the config route:

```python
@app.get("/api/config", response_model=FrontendConfigResponse)
async def config() -> dict[str, Any]:
    """Return frontend configuration values."""
    return read_frontend_config()
```

- [ ] **Step 4: Update CLI direct mode dotenv loading**

In `src/news/cli/fetch.py`, replace local project-root path arithmetic with:

```python
from news.web.paths import env_path
```

and inside `fetch_direct_page`:

```python
load_dotenv(env_path())
```

- [ ] **Step 5: Add config/path test coverage**

Append to `tests/test_app.py`:

```python
class RuntimePathTests(unittest.TestCase):
    """Verify project-root resource helpers resolve expected files."""

    def test_runtime_paths_find_frontend_and_config(self) -> None:
        """Path helpers should locate root resources from the src package."""
        from news.web.paths import config_path, frontend_dir, project_root

        self.assertTrue((project_root() / "pyproject.toml").exists())
        self.assertTrue(config_path().exists())
        self.assertTrue((frontend_dir() / "index.html").exists())
```

- [ ] **Step 6: Run route and path tests**

Run:

```bash
uv run python -m unittest tests.test_app -v
```

Expected: pass.

- [ ] **Step 7: Commit runtime helper extraction**

```bash
git add src/news/web src/news/api/app.py src/news/cli/fetch.py tests/test_app.py
git commit -m "refactor: centralize runtime paths and config"
```

---

### Task 5: Split API Query Parameters Out Of App Module

**Files:**
- Create: `src/news/api/params.py`
- Modify: `src/news/api/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Move `SearchQueryParams` and `_split_csv_values`**

Create `src/news/api/params.py` with:

```python
"""HTTP query parameter parsing for news search routes."""

from __future__ import annotations

from fastapi import Query

from news.search import build_search_request
from news.search.models import SearchRequest


class SearchQueryParams:
    """Dependency object for the public search query parameters."""

    def __init__(
        self,
        q: str = Query(..., description="Keyword or boolean query"),
        start: str = Query(..., description="Start date (YYYY-MM-DD)"),
        end: str = Query(..., description="End date (YYYY-MM-DD)"),
        sources: str = Query(
            default="",
            description="Comma-separated source names (default: all available)",
        ),
        language: str = Query(
            default="",
            description=(
                "Language filter such as 'en', 'english', or 'en-US'. "
                "Provider labels are normalized before comparison."
            ),
        ),
        dedupe: bool = Query(
            default=True,
            description="Collapse duplicate articles that appear across sources",
        ),
        exact_phrase: str = Query(
            default="",
            description="Optional exact phrase to require in post-filtering",
        ),
        exclude_terms: str = Query(
            default="",
            description="Comma-separated terms to exclude from results",
        ),
        domain: str = Query(
            default="",
            description="Comma-separated domains to include in local filtering",
        ),
        exclude_domains: str = Query(
            default="",
            description="Comma-separated domains to exclude in local filtering",
        ),
        search_scope: str = Query(default="all", description="Local filter scope"),
        match_mode: str = Query(default="provider", description="Keyword match mode"),
        provider_sort: str = Query(default="default", description="Provider sort mode"),
        section: str = Query(default="", description="Comma-separated sections"),
        news_desk: str = Query(default="", description="Comma-separated NYT desks"),
        guardian_tag: str = Query(default="", description="Comma-separated tags"),
        newsapi_search_in: str = Query(default="all", description="NewsAPI field scope"),
        sort: str = Query(default="date_desc", description="Sort order"),
        page: int = Query(default=1, ge=1, description="1-based provider page"),
    ) -> None:
        self.q = q
        self.start = start
        self.end = end
        self.sources = sources
        self.language = language
        self.dedupe = dedupe
        self.exact_phrase = exact_phrase
        self.exclude_terms = exclude_terms
        self.domain = domain
        self.exclude_domains = exclude_domains
        self.search_scope = search_scope
        self.match_mode = match_mode
        self.provider_sort = provider_sort
        self.section = section
        self.news_desk = news_desk
        self.guardian_tag = guardian_tag
        self.newsapi_search_in = newsapi_search_in
        self.sort = sort
        self.page = page

    def to_search_request(self) -> SearchRequest:
        """Convert query parameters into the validated search request."""
        return build_search_request(
            query=self.q,
            start_date=self.start,
            end_date=self.end,
            source_names=split_csv_values(self.sources),
            language=self.language,
            deduplicate=self.dedupe,
            exact_phrase=self.exact_phrase,
            exclude_terms=self.exclude_terms,
            domain_filter=self.domain,
            exclude_domains=self.exclude_domains,
            search_scope=self.search_scope,
            match_mode=self.match_mode,
            provider_sort=self.provider_sort,
            section=self.section,
            news_desk=self.news_desk,
            guardian_tag=self.guardian_tag,
            newsapi_search_in=self.newsapi_search_in,
            sort_order=self.sort,
            page=self.page,
        )


def split_csv_values(raw_value: str) -> list[str] | None:
    """Split comma-separated query parameters and drop blank entries."""
    cleaned_values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not cleaned_values:
        return None
    return cleaned_values
```

- [ ] **Step 2: Simplify `src/news/api/app.py`**

Remove the in-file `SearchQueryParams` class and `_split_csv_values` function.
Import params instead:

```python
from news.api.params import SearchQueryParams
```

- [ ] **Step 3: Run route tests**

Run:

```bash
uv run python -m unittest tests.test_app -v
```

Expected: pass.

- [ ] **Step 4: Commit API parameter split**

```bash
git add src/news/api tests/test_app.py
git commit -m "refactor: split api query parameter parsing"
```

---

### Task 6: Add Canonical Package Entry Points

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/news/api/app.py`
- Modify: `src/news/cli/workflow.py`
- Delete: `main.py`
- Delete: `cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add project scripts to `pyproject.toml`**

Add this table below the `[project]` table:

```toml
[project.scripts]
news-server = "news.api.app:main"
news-search = "news.cli.workflow:main"
```

- [ ] **Step 2: Add `main()` to `src/news/api/app.py`**

Append:

```python
def main() -> None:
    """Start the local FastAPI development server."""
    import uvicorn

    uvicorn.run(
        "news.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Ensure CLI workflow already exposes `main`**

Check `src/news/cli/workflow.py` still has:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
```

Append this script execution guard if missing:

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Remove old root wrappers**

Run:

```bash
git rm main.py cli.py
```

- [ ] **Step 5: Run script metadata tests**

Run:

```bash
uv run python -m unittest tests.test_cli.PackageEntryPointTests -v
```

Expected: pass.

- [ ] **Step 6: Run package command smoke checks**

Run:

```bash
uv run python -m news.cli.workflow "inflation" -s 2025-01-01 -e 2025-01-02 --sources gdelt --direct --json --quiet
```

Expected: command exits `0` and prints a JSON object with `results` and `meta`.
If the live GDELT request fails because the network or upstream service is
unavailable, record the exact error and rely on unittest coverage for automated
verification.

Run:

```bash
uv run python -c "from news.api.app import app; print(app.title)"
```

Expected output:

```text
Historical News Search Engine
```

- [ ] **Step 7: Commit entry point changes**

```bash
git add pyproject.toml src/news/api/app.py src/news/cli/workflow.py tests/test_cli.py
git add -u main.py cli.py
git commit -m "refactor: add package entry points"
```

---

### Task 7: Update Documentation And Guide Files

**Files:**
- Create: `src/GUIDE_src.md`
- Create: `src/news/GUIDE_news.md`
- Modify: `README.md`
- Modify: `GUIDE_ROOT.md`
- Modify: `PROJECT_STRUCTURE.md`
- Modify: `PROJECT_OVERVIEW.md` if any command or package wording is stale
- Modify: `tests/GUIDE_tests.md`

- [ ] **Step 1: Update `README.md` quick start**

Replace old root commands with:

```markdown
```bash
uv sync
uv run news-server
uv run news-search "inflation" -s 2025-01-01 -e 2025-03-01
```
```

State that product code lives in `src/news/`.

- [ ] **Step 2: Add `src/GUIDE_src.md`**

Use this content:

```markdown
# GUIDE_src

## Purpose

The `src/` folder contains importable Python product code. Non-product assets
such as tests, notebooks, static frontend files, and generated outputs stay at
the project root outside `src/`.

## Folder Map

- `news/`: historical multi-source news retrieval package.

## Development Notes

- Use `uv run news-server` to start the local API and frontend server.
- Use `uv run news-search ...` for command-line search and export workflows.
- Keep reusable Python logic under `src/news/`.
```

- [ ] **Step 3: Add `src/news/GUIDE_news.md`**

Document these package responsibilities:

```markdown
# GUIDE_news

## Purpose

The `news` package is the product implementation for historical multi-source
news retrieval.

## Subpackages

- `api/`: FastAPI app, route models, and query parameter parsing.
- `search/`: validation, cache, filtering, deduplication, sorting, and result metadata.
- `sources/`: source registry, fan-out, retry behavior, and provider adapters.
- `exports/`: CSV, JSON, and SQLite serialization.
- `cli/`: command-line parser, fetch paths, output rendering, and workflow orchestration.
- `web/`: project-root path and configuration helpers.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected providers, applies local filters and optional deduplication,
sorts the final page, and returns normalized article rows plus metadata.
```

- [ ] **Step 4: Update root guides**

Update `GUIDE_ROOT.md` and `PROJECT_STRUCTURE.md` so they show:

```text
src/news/       -- Importable product package.
frontend/       -- Static browser UI served by the API.
tests/          -- unittest coverage for API, search, sources, exports, CLI, and frontend static checks.
API_explorer/   -- Notebook-led upstream API reconnaissance.
website/        -- API reference snapshot.
```

Remove references to `backend/`, `main.py`, and root `cli.py`.

- [ ] **Step 5: Update `tests/GUIDE_tests.md`**

Replace `backend...` import language with `news...` import language and remove
the old root CLI compatibility note.

- [ ] **Step 6: Run documentation consistency scan**

Run:

```bash
rg -n "backend/|backend\.|main\.py|cli\.py|uv run python main|uv run python cli" README.md GUIDE_ROOT.md PROJECT_STRUCTURE.md PROJECT_OVERVIEW.md tests/GUIDE_tests.md src -g '!docs/superpowers/**'
```

Expected: no stale references in active product documentation.

- [ ] **Step 7: Commit documentation updates**

```bash
git add README.md GUIDE_ROOT.md PROJECT_STRUCTURE.md PROJECT_OVERVIEW.md tests/GUIDE_tests.md src/GUIDE_src.md src/news/GUIDE_news.md
git commit -m "docs: update guides for src news package"
```

---

### Task 8: Full Verification And Cleanup

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run import and stale-path scans**

Run:

```bash
rg -n "from backend|import backend|backend\.|backend/" src tests README.md GUIDE_ROOT.md PROJECT_STRUCTURE.md PROJECT_OVERVIEW.md tests/GUIDE_tests.md
```

Expected: no output.

Run:

```bash
find . -maxdepth 3 -type d -name backend -print
```

Expected: no output.

- [ ] **Step 2: Run Ruff**

Run:

```bash
uv run ruff check .
```

Expected: pass. Fix import ordering, unused imports, or line-length failures
without changing behavior.

- [ ] **Step 3: Run full unittest suite**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected: pass.

- [ ] **Step 4: Run command smoke checks**

Run:

```bash
uv run python -c "from news.api.app import app; print(app.title)"
```

Expected:

```text
Historical News Search Engine
```

Run:

```bash
uv run news-search "inflation" -s 2025-01-01 -e 2025-01-02 --sources gdelt --direct --json --quiet
```

Expected: command exits `0` and prints JSON with top-level `results` and `meta`.
If this live provider check fails for upstream or network reasons, keep the
failure output in the final implementation notes and confirm unit tests passed.

- [ ] **Step 5: Review git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only planned refactor, test, and documentation files are changed.

- [ ] **Step 6: Commit verification fixes**

If Step 2, 3, or 4 required fixes, commit them:

```bash
git add .
git commit -m "fix: complete product package verification"
```

If no fixes were required, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan implements the approved `src/news/` package-first
  structure, removes old compatibility files, preserves product capabilities,
  adds package scripts, updates tests, updates guide files, and verifies the
  package behavior.
- Placeholder scan: No task uses `TBD`, `TODO`, or unspecified "add appropriate"
  work. Each step names exact files, commands, and expected outcomes.
- Type and name consistency: Canonical package name is `news`; canonical scripts
  are `news-server` and `news-search`; API app object remains `app`; CLI entry
  remains `main(argv: list[str] | None = None) -> int`.
