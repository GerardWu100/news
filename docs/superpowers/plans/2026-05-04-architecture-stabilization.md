# Architecture Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix confirmed correctness and security bugs, then reduce architectural coupling around validation, source registration, state, and the command-line interface.

**Architecture:** Stabilize behavior first with regression tests, then improve boundaries without changing the product scope. Keep the FastAPI route layer thin, move framework-independent logic into backend modules, make shared state explicit, and split the oversized CLI into focused modules while preserving the existing root `cli.py` entry point.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, httpx, unittest, Ruff, vanilla JavaScript frontend, SQLite.

---

## File Structure

- Modify: `backend/search/filters.py`
  - Owns local filtering and sorting rules. Fix language matching and date-title sort behavior here.
- Modify: `backend/search/validation.py`
  - Keeps raw search parameter normalization. Replace silent NewsAPI scope fallback with explicit invalid-input rejection.
- Create: `backend/search/errors.py`
  - New framework-independent exception type for search validation errors.
- Modify: `backend/app.py`
  - Maps project-owned validation errors to FastAPI `HTTPException` at the HTTP boundary.
- Modify: `backend/export.py`
  - Closes SQLite connections deterministically after export writes.
- Modify: `frontend/scripts/render.js`
  - Escapes and validates article links before rendering the article dialog.
- Create: `backend/sources/registry.py`
  - New source registry module that owns adapter construction and source-name lookup.
- Modify: `backend/sources/__init__.py`
  - Re-export source registry functions and keep fan-out orchestration small.
- Modify: `backend/search/service.py`
  - Remove module-default cache binding from the function signature and make default state explicit inside the function body.
- Modify: `backend/sources/mediacloud.py`
  - Replace unbounded module-level pagination token dictionary with a small expiring token store.
- Modify: `cli.py`
  - Keep as thin root entry point for backwards-compatible command usage.
- Create: `backend/cli/__init__.py`
  - Package marker for CLI implementation modules.
- Create: `backend/cli/parser.py`
  - Argument parser and API parameter mapping.
- Create: `backend/cli/fetch.py`
  - API and direct backend fetch paths.
- Create: `backend/cli/output.py`
  - Table rendering and export writing.
- Create: `backend/cli/workflow.py`
  - Top-level CLI orchestration and all-pages aggregation.
- Modify: `tests/test_search_service.py`
  - Add regression tests for language filtering, NewsAPI validation, sort ties, and validation error mapping.
- Modify: `tests/test_export.py`
  - Add SQLite connection closure regression test.
- Modify: `tests/test_cli.py`
  - Update imports to the new CLI modules while keeping root `cli.py` smoke coverage.
- Add: `tests/test_frontend_static.py`
  - Static regression check that rendered links are sanitized through a helper.
- Modify: `GUIDE_ROOT.md`, `backend/GUIDE_backend.md`, `tests/GUIDE_tests.md`, `PROJECT_STRUCTURE.md`
  - Update developer navigation after code movement and behavior changes.

## Confirmed Bugs To Fix First

| Severity | Bug | Evidence | Fix direction |
|---|---|---|---|
| High | Provider URL rendered directly into frontend `href` | `frontend/scripts/render.js` inserts `result.url` in an HTML attribute | Sanitize allowed protocols and escape attribute values |
| Medium | English filter matches French | `language='en'` matches `"french"` because of substring matching | Normalize language labels to exact codes or known names |
| Medium | Invalid `newsapi_search_in` becomes `all` | `banana` normalizes to `all` | Reject unknown fields before canonicalization |
| Medium | SQLite export leaves connection unclosed | Test run emits `ResourceWarning` | Use `contextlib.closing(sqlite3.connect(...))` |
| Low | Same-date descending sort reverses title order | Date descending reverses the whole `(date, title)` tuple | Sort by date direction and title ascending |

## Task 1: Add Bug Regression Tests

**Files:**
- Modify: `tests/test_search_service.py`
- Modify: `tests/test_export.py`
- Add: `tests/test_frontend_static.py`

- [ ] **Step 1: Add language, NewsAPI, and sort regression tests**

Add these test methods to `BuildSearchRequestTests` and a new `FilterBehaviorTests` class in `tests/test_search_service.py`.

```python
class FilterBehaviorTests(unittest.TestCase):
    """Check local filter behavior that can quietly distort research output."""

    def test_language_filter_does_not_match_french_when_requesting_english(self) -> None:
        """The English shortcut should not keep French-language rows."""
        from backend.search.filters import filter_by_language

        articles = [
            Article(
                title="French story",
                url="https://example.com/fr",
                date="2026-01-01",
                source="test",
                language="french",
            ),
            Article(
                title="English story",
                url="https://example.com/en",
                date="2026-01-01",
                source="test",
                language="english",
            ),
            Article(
                title="ISO English story",
                url="https://example.com/iso",
                date="2026-01-01",
                source="test",
                language="en",
            ),
            Article(
                title="Unknown language story",
                url="https://example.com/unknown",
                date="2026-01-01",
                source="test",
                language="",
            ),
        ]

        filtered = filter_by_language(articles, "en")

        self.assertEqual(
            [article.title for article in filtered],
            ["English story", "ISO English story", "Unknown language story"],
        )

    def test_date_desc_sort_keeps_title_ascending_inside_same_date(self) -> None:
        """Date descending should not reverse alphabetical title ties."""
        from backend.search.filters import sort_articles

        articles = [
            Article(
                title="Zulu",
                url="https://example.com/z",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Alpha",
                url="https://example.com/a",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Beta",
                url="https://example.com/b",
                date="2026-01-02",
                source="test",
            ),
        ]

        sorted_articles = sort_articles(articles, "date_desc")

        self.assertEqual(
            [article.title for article in sorted_articles],
            ["Beta", "Alpha", "Zulu"],
        )
```

Add this method to `BuildSearchRequestTests`.

```python
def test_rejects_invalid_newsapi_search_scope(self) -> None:
    """Unknown NewsAPI field scopes should fail instead of broadening search."""
    with self.assertRaises(HTTPException) as context:
        build_search_request(
            query="inflation",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=None,
            language="",
            deduplicate=True,
            newsapi_search_in="banana",
        )

    self.assertEqual(context.exception.status_code, 422)
    self.assertIn("newsapi_search_in", context.exception.detail)
```

- [ ] **Step 2: Add SQLite closure regression test**

Add this method to `SqliteExportTests` in `tests/test_export.py`.

```python
def test_write_sqlite_closes_connection_without_resource_warning(self) -> None:
    """SQLite export should not leak a connection after writing rows."""
    import gc
    import warnings

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            write_sqlite(SAMPLE_ARTICLES, str(db_path), query="fed")
            gc.collect()

    resource_warnings = [
        warning
        for warning in caught
        if issubclass(warning.category, ResourceWarning)
    ]
    self.assertEqual(resource_warnings, [])
```

- [ ] **Step 3: Add static frontend link-sanitizer regression**

Create `tests/test_frontend_static.py`.

```python
"""Static checks for frontend security-sensitive rendering helpers."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENDER_JS_PATH = PROJECT_ROOT / "frontend" / "scripts" / "render.js"


class FrontendStaticSecurityTests(unittest.TestCase):
    """Check that provider-controlled URLs go through explicit sanitization."""

    def test_article_dialog_uses_safe_url_helper_for_links(self) -> None:
        """Article links should not render raw provider URLs into href."""
        render_source = RENDER_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("function buildSafeArticleUrl", render_source)
        self.assertIn("const safeUrl = buildSafeArticleUrl(result.url)", render_source)
        self.assertNotIn('href="${result.url}"', render_source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the new tests and confirm they fail**

Run:

```bash
uv run python -m unittest tests.test_search_service tests.test_export tests.test_frontend_static -v
```

Expected:
- Language filter test fails because French is kept.
- NewsAPI scope test fails because `"banana"` normalizes to `"all"`.
- Sort tie test fails because `"Zulu"` appears before `"Alpha"` on the same date.
- SQLite closure test fails with a `ResourceWarning`.
- Frontend static test fails because `buildSafeArticleUrl` does not exist.

- [ ] **Step 5: Commit failing tests**

Run:

```bash
git add tests/test_search_service.py tests/test_export.py tests/test_frontend_static.py
git commit -m "test: capture architecture stabilization regressions"
```

## Task 2: Fix Confirmed Bugs

**Files:**
- Modify: `backend/search/filters.py`
- Modify: `backend/search/validation.py`
- Modify: `backend/export.py`
- Modify: `frontend/scripts/render.js`

- [ ] **Step 1: Fix language matching and date-title sorting**

In `backend/search/filters.py`, add language alias constants near the top of the file.

```python
LANGUAGE_ALIASES = {
    "en": {"en", "eng", "english"},
    "fr": {"fr", "fre", "fra", "french"},
    "es": {"es", "spa", "spanish"},
}
```

Replace `filter_by_language(...)` with:

```python
def filter_by_language(
    articles: Sequence[Article],
    language: str,
) -> list[Article]:
    """Apply a language filter without substring false positives."""
    if not language:
        return list(articles)

    requested_language = normalize_language_label(language)
    accepted_labels = LANGUAGE_ALIASES.get(requested_language, {requested_language})

    filtered_articles: list[Article] = []
    for article in articles:
        article_language = normalize_language_label(article.language)
        if not article_language:
            filtered_articles.append(article)
            continue
        if article_language in accepted_labels:
            filtered_articles.append(article)

    return filtered_articles
```

Add this helper below `filter_by_language(...)`.

```python
def normalize_language_label(value: str) -> str:
    """Normalize provider language labels into comparable lowercase tokens."""
    cleaned_value = value.strip().lower()
    if not cleaned_value:
        return ""

    first_token = re.split(r"[^a-z]+", cleaned_value, maxsplit=1)[0]
    for canonical_label, aliases in LANGUAGE_ALIASES.items():
        if first_token in aliases:
            return canonical_label

    return first_token
```

Replace `sort_articles(...)` with:

```python
def sort_articles(articles: Sequence[Article], sort_order: str) -> list[Article]:
    """Sort articles by date while keeping title ties alphabetical."""
    if sort_order == "date_asc":
        return sorted(
            articles,
            key=lambda article: (article.date, article.title.lower()),
        )

    return sorted(
        articles,
        key=lambda article: (_descending_date_key(article.date), article.title.lower()),
    )
```

Add this helper below `sort_articles(...)`.

```python
def _descending_date_key(date_value: str) -> str:
    """Return an inverted ISO date key for descending lexical sorting."""
    if not date_value:
        return "9999-99-99"

    digits = date_value.replace("-", "")
    if len(digits) != 8 or not digits.isdigit():
        return "9999-99-99"

    inverted_number = 99999999 - int(digits)
    inverted_text = str(inverted_number).zfill(8)
    return f"{inverted_text[:4]}-{inverted_text[4:6]}-{inverted_text[6:8]}"
```

- [ ] **Step 2: Reject invalid NewsAPI search fields**

In `backend/search/validation.py`, replace `_normalize_search_in(...)` with:

```python
def _normalize_search_in(raw_value: str) -> str:
    """Canonicalize NewsAPI ``searchIn`` values and reject unknown fields."""
    cleaned = raw_value.strip().lower()
    if not cleaned:
        return "all"

    fields = [field.strip() for field in cleaned.split(",") if field.strip()]
    if not fields:
        return "all"

    allowed_fields = {"title", "description", "content"}
    unknown_fields = [field for field in fields if field not in allowed_fields]
    if unknown_fields:
        invalid_values = ", ".join(unknown_fields)
        allowed_values = ", ".join(sorted(ALLOWED_NEWSAPI_SEARCH_IN))
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid newsapi_search_in value "
                f"'{invalid_values}'. Allowed values: {allowed_values}"
            ),
        )

    ordered_fields = [
        field for field in ("title", "description", "content") if field in fields
    ]
    normalized = ",".join(dict.fromkeys(ordered_fields))
    return normalized or "all"
```

- [ ] **Step 3: Close SQLite connections deterministically**

In `backend/export.py`, import `closing`.

```python
from contextlib import closing
```

Replace the opening line of `write_sqlite(...)`.

```python
with closing(sqlite3.connect(db_path)) as connection:
    with connection:
        connection.execute(_SQLITE_SCHEMA)
```

Keep the schema, index, and insert logic inside the inner `with connection:` block so commits and rollback behavior remain unchanged while the connection closes after the outer context exits.

- [ ] **Step 4: Sanitize frontend article links**

In `frontend/scripts/render.js`, replace `createArticleDialogContent(...)` with:

```javascript
function createArticleDialogContent(result) {
    const bodyText = result.content || result.summary || "No provider text available for this record.";
    const safeUrl = buildSafeArticleUrl(result.url);
    const articleLink = safeUrl
        ? `<a class="article-dialog-link" href="${escapeAttribute(safeUrl)}" target="_blank" rel="noopener noreferrer">Open original article</a>`
        : "";

    return `
        <div class="article-dialog-header">
            <div class="article-dialog-badges">${renderSourceBadges(result)}</div>
            <h2>${escapeHtml(result.title || "Untitled")}</h2>
            <div class="article-dialog-meta">
                ${result.date ? `<span>${escapeHtml(result.date)}</span>` : ""}
                ${result.domain ? `<span>${escapeHtml(result.domain)}</span>` : ""}
                ${result.section ? `<span>${escapeHtml(result.section)}</span>` : ""}
                ${result.author ? `<span>${escapeHtml(result.author)}</span>` : ""}
            </div>
        </div>
        ${result.summary ? `<p class="article-dialog-summary">${escapeHtml(result.summary)}</p>` : ""}
        <div class="article-dialog-text">${escapeHtml(bodyText)}</div>
        ${articleLink}
    `;
}
```

Add these helpers below `createArticleDialogContent(...)`.

```javascript
function buildSafeArticleUrl(rawUrl) {
    if (!rawUrl) {
        return "";
    }

    try {
        const parsedUrl = new URL(rawUrl, window.location.origin);
        if (parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:") {
            return parsedUrl.href;
        }
    } catch {
        return "";
    }

    return "";
}


function escapeAttribute(value) {
    return escapeHtml(value).replace(/"/g, "&quot;");
}
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
uv run python -m unittest tests.test_search_service tests.test_export tests.test_frontend_static -v
```

Expected:
- All focused tests pass.
- No SQLite `ResourceWarning` appears.

- [ ] **Step 6: Run full verification**

Run:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
```

Expected:
- Ruff passes.
- All tests pass.
- No `ResourceWarning` appears.

- [ ] **Step 7: Commit bug fixes**

Run:

```bash
git add backend/search/filters.py backend/search/validation.py backend/export.py frontend/scripts/render.js
git commit -m "fix: stabilize search filtering export and link rendering"
```

## Task 3: Decouple Validation From FastAPI And Global Sources

**Files:**
- Create: `backend/search/errors.py`
- Modify: `backend/search/validation.py`
- Modify: `backend/app.py`
- Modify: `tests/test_search_service.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Add framework-independent validation exception**

Create `backend/search/errors.py`.

```python
"""Project-owned exceptions for search request validation."""

from __future__ import annotations


class SearchValidationError(ValueError):
    """Raised when raw search inputs cannot become a valid search request."""

    def __init__(self, message: str) -> None:
        """Store the human-readable validation message."""
        super().__init__(message)
        self.message = message
```

- [ ] **Step 2: Replace FastAPI exceptions in validation**

In `backend/search/validation.py`:

- Remove `from fastapi import HTTPException`.
- Add `from .errors import SearchValidationError`.
- Replace each `raise HTTPException(status_code=422, detail="...")` with `raise SearchValidationError("...")`.

The date parsing failure should become:

```python
raise SearchValidationError(f"Invalid {field_name} date, expected YYYY-MM-DD") from exc
```

The invalid choice failure should become:

```python
raise SearchValidationError(
    f"Invalid {field_name}. Allowed values: {allowed}"
)
```

- [ ] **Step 3: Map validation errors in the FastAPI boundary**

In `backend/app.py`, import `HTTPException` and `SearchValidationError`.

```python
from fastapi import Depends, FastAPI, HTTPException, Query
from .search.errors import SearchValidationError
```

Replace `_run_search_request(...)` with:

```python
async def _run_search_request(params: SearchQueryParams):
    """Validate request parameters and run the shared search pipeline."""
    try:
        request = params.to_search_request()
    except SearchValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return await run_search(request)
```

- [ ] **Step 4: Update tests for project-owned validation errors**

In `tests/test_search_service.py`, replace:

```python
from fastapi import HTTPException
```

with:

```python
from backend.search.errors import SearchValidationError
```

Update validation tests to expect `SearchValidationError` and assert `str(context.exception)` or `context.exception.message` instead of `status_code`.

Example:

```python
with self.assertRaises(SearchValidationError) as context:
    build_search_request(...)

self.assertIn("Start date", context.exception.message)
```

Keep `tests/test_app.py` route tests asserting HTTP status behavior so the API mapping stays protected.

- [ ] **Step 5: Run validation and app tests**

Run:

```bash
uv run python -m unittest tests.test_search_service tests.test_app -v
```

Expected:
- Pure search tests pass with `SearchValidationError`.
- FastAPI route tests still return HTTP responses with status `422` for invalid requests.

- [ ] **Step 6: Commit validation decoupling**

Run:

```bash
git add backend/search/errors.py backend/search/validation.py backend/app.py tests/test_search_service.py tests/test_app.py
git commit -m "refactor: decouple search validation from FastAPI"
```

## Task 4: Introduce Source Registry Boundary

**Files:**
- Create: `backend/sources/registry.py`
- Modify: `backend/sources/__init__.py`
- Modify: `backend/search/validation.py`
- Modify: `tests/test_search_service.py`

- [ ] **Step 1: Create explicit source registry module**

Create `backend/sources/registry.py`.

```python
"""Source adapter registry and source-name lookup helpers."""

from __future__ import annotations

from .acled import AcledSource
from .base import BaseSource
from .guardian import GuardianSource
from .gdelt import GdeltSource
from .mediacloud import MediaCloudSource
from .newsapi import NewsApiSource
from .nyt import NewYorkTimesSource


def build_default_sources() -> list[BaseSource]:
    """Construct the default ordered provider adapter list."""
    return [
        GdeltSource(),
        MediaCloudSource(),
        AcledSource(),
        NewYorkTimesSource(),
        GuardianSource(),
        NewsApiSource(),
    ]


ALL_SOURCES: list[BaseSource] = build_default_sources()


def source_names() -> set[str]:
    """Return the registered provider names."""
    return {source.name for source in ALL_SOURCES}
```

- [ ] **Step 2: Re-export registry from source package**

In `backend/sources/__init__.py`:

- Remove adapter class imports.
- Remove the inline `ALL_SOURCES` construction.
- Add:

```python
from .registry import ALL_SOURCES, source_names
```

- [ ] **Step 3: Use registry lookup in validation**

In `backend/search/validation.py`, replace:

```python
from ..sources import ALL_SOURCES
```

with:

```python
from ..sources.registry import source_names
```

Replace:

```python
known_sources = {source.name for source in ALL_SOURCES}
```

with:

```python
known_sources = source_names()
```

- [ ] **Step 4: Run source and validation tests**

Run:

```bash
uv run python -m unittest tests.test_search_service tests.test_app -v
```

Expected:
- Source fan-out tests and validation tests pass.
- Unknown source messages still list the allowed provider names.

- [ ] **Step 5: Commit source registry boundary**

Run:

```bash
git add backend/sources/registry.py backend/sources/__init__.py backend/search/validation.py tests/test_search_service.py
git commit -m "refactor: isolate source registry lookup"
```

## Task 5: Make Shared Runtime State Explicit

**Files:**
- Modify: `backend/search/service.py`
- Modify: `backend/sources/mediacloud.py`
- Modify: `tests/test_cache.py`
- Modify: `tests/test_search_service.py`

- [ ] **Step 1: Remove default cache object from function signature**

In `backend/search/service.py`, change the `run_search(...)` signature from:

```python
cache: SearchResultCache | None = DEFAULT_SEARCH_CACHE,
```

to:

```python
cache: SearchResultCache | None = None,
```

Add this near the top of the function body after the docstring:

```python
active_cache = DEFAULT_SEARCH_CACHE if cache is None else cache
```

Then replace `cache.get(...)` and `cache.set(...)` uses with `active_cache.get(...)` and `active_cache.set(...)`.

Keep `use_cache=False` bypassing cache work:

```python
if use_cache:
    cached_result = active_cache.get(request)
```

- [ ] **Step 2: Preserve tests that inject custom caches**

In `tests/test_cache.py`, verify any test that passes a custom cache still calls:

```python
await run_search(request, executor=fake_executor, cache=cache)
```

Add this test if it is missing:

```python
async def test_run_search_accepts_explicit_cache_instance(self) -> None:
    """Callers should be able to provide an isolated cache."""
    cache = SearchResultCache(ttl_seconds=60, max_entries=10)
    request = build_search_request(
        query="rates",
        start_date="2026-01-01",
        end_date="2026-01-02",
        source_names=("gdelt",),
        language="",
        deduplicate=True,
    )

    calls = 0

    async def fake_executor(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return [], []

    await run_search(request, executor=fake_executor, cache=cache)
    await run_search(request, executor=fake_executor, cache=cache)

    self.assertEqual(calls, 1)
```

- [ ] **Step 3: Replace MediaCloud pagination dictionary with bounded store**

In `backend/sources/mediacloud.py`, add:

```python
from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Callable
```

Replace `_PAGINATION_TOKENS` with:

```python
MEDIACLOUD_TOKEN_TTL_SECONDS = 900
MEDIACLOUD_TOKEN_MAX_KEYS = 200


@dataclass(frozen=True, slots=True)
class PaginationTokenEntry:
    """One cached MediaCloud continuation token."""

    stored_at: float
    token: str


class PaginationTokenStore:
    """Small expiring cache for MediaCloud continuation tokens."""

    def __init__(
        self,
        ttl_seconds: int = MEDIACLOUD_TOKEN_TTL_SECONDS,
        max_keys: int = MEDIACLOUD_TOKEN_MAX_KEYS,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Create a bounded token store."""
        self.ttl_seconds = ttl_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._tokens: OrderedDict[
            tuple[object, ...],
            dict[int, PaginationTokenEntry],
        ] = OrderedDict()

    def get(self, key: tuple[object, ...], page: int) -> str:
        """Return a live token for one query/page pair."""
        self._evict_expired()
        page_tokens = self._tokens.get(key, {})
        entry = page_tokens.get(page)
        if entry is None:
            return ""
        if self._clock() - entry.stored_at >= self.ttl_seconds:
            page_tokens.pop(page, None)
            return ""
        self._tokens.move_to_end(key)
        return entry.token

    def set(self, key: tuple[object, ...], page: int, token: str) -> None:
        """Store the token needed to fetch a future page."""
        if not token:
            return
        self._evict_expired()
        page_tokens = self._tokens.setdefault(key, {})
        page_tokens[page] = PaginationTokenEntry(
            stored_at=self._clock(),
            token=token,
        )
        self._tokens.move_to_end(key)
        while len(self._tokens) > self.max_keys:
            self._tokens.popitem(last=False)

    def _evict_expired(self) -> None:
        """Drop expired query/page token entries."""
        now = self._clock()
        empty_keys: list[tuple[object, ...]] = []
        for key, page_tokens in self._tokens.items():
            expired_pages = [
                page
                for page, entry in page_tokens.items()
                if now - entry.stored_at >= self.ttl_seconds
            ]
            for page in expired_pages:
                page_tokens.pop(page, None)
            if not page_tokens:
                empty_keys.append(key)
        for key in empty_keys:
            self._tokens.pop(key, None)


_PAGINATION_TOKENS = PaginationTokenStore()
```

Update `_lookup_pagination_token(...)`:

```python
token_key = _build_pagination_key(options)
return _PAGINATION_TOKENS.get(token_key, options.page)
```

Update `_store_next_page_token(...)`:

```python
key = _build_pagination_key(options)
_PAGINATION_TOKENS.set(key, options.page + 1, token)
```

- [ ] **Step 4: Add MediaCloud token store unit test**

Add this test class to `tests/test_search_service.py`.

```python
class MediaCloudPaginationTokenStoreTests(unittest.TestCase):
    """Check bounded continuation-token behavior for MediaCloud pagination."""

    def test_token_store_expires_old_entries(self) -> None:
        """Expired pagination tokens should not be reused."""
        from backend.sources.mediacloud import PaginationTokenStore

        current_time = 100.0

        def fake_clock() -> float:
            return current_time

        store = PaginationTokenStore(ttl_seconds=10, max_keys=2, clock=fake_clock)
        key = ("query", "2026-01-01", "2026-01-02")

        store.set(key, 2, "abc")
        self.assertEqual(store.get(key, 2), "abc")

        current_time = 111.0
        self.assertEqual(store.get(key, 2), "")
```

- [ ] **Step 5: Run state-related tests**

Run:

```bash
uv run python -m unittest tests.test_cache tests.test_search_service -v
```

Expected:
- Cache tests pass.
- MediaCloud cooldown and pagination token tests pass.

- [ ] **Step 6: Commit runtime state cleanup**

Run:

```bash
git add backend/search/service.py backend/sources/mediacloud.py tests/test_cache.py tests/test_search_service.py
git commit -m "refactor: make search runtime state explicit"
```

## Task 6: Split CLI Responsibilities

**Files:**
- Create: `backend/cli/__init__.py`
- Create: `backend/cli/parser.py`
- Create: `backend/cli/fetch.py`
- Create: `backend/cli/output.py`
- Create: `backend/cli/workflow.py`
- Modify: `cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Create CLI package marker**

Create `backend/cli/__init__.py`.

```python
"""Command-line workflow modules for the news search project."""
```

- [ ] **Step 2: Move parser code into `backend/cli/parser.py`**

Move these items from root `cli.py` to `backend/cli/parser.py`:

- `DEFAULT_EXPORT_MAX_PAGES`
- `DEFAULT_SERVER_URL`
- `DEFAULT_PROVIDER_SORT`
- `build_arg_parser(...)`
- `build_api_params(...)`
- `_split_csv_argument(...)`

Keep imports local to parser needs:

```python
from __future__ import annotations

import argparse
```

- [ ] **Step 3: Move fetch code into `backend/cli/fetch.py`**

Move these functions from root `cli.py` to `backend/cli/fetch.py`:

- `_fetch_page(...)`
- `_fetch_api_page(...)`
- `_fetch_direct_page(...)`

Use imports:

```python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from .parser import build_api_params, split_csv_argument
```

Rename `_split_csv_argument(...)` to `split_csv_argument(...)` in parser and update fetch imports.

- [ ] **Step 4: Move output code into `backend/cli/output.py`**

Move these functions from root `cli.py` to `backend/cli/output.py`:

- `format_table(...)`
- `_truncate(...)`
- `_write_export(...)`
- `_download_api_export(...)`
- `_should_download_api_export(...)`
- `_resolve_output_path(...)`

Use imports:

```python
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from backend.export import format_csv, format_json, write_sqlite
from .parser import build_api_params
```

Expose public names without leading underscores where tests use them:

- `write_export(...)`
- `resolve_output_path(...)`

- [ ] **Step 5: Move workflow code into `backend/cli/workflow.py`**

Move these functions from root `cli.py` to `backend/cli/workflow.py`:

- `main(...)`
- `_run_cli(...)`
- `_collect_results(...)`
- `_collect_all_pages(...)`

Use imports:

```python
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any

import httpx

from backend.search.errors import SearchValidationError
from .fetch import fetch_page
from .output import format_table, resolve_output_path, write_export
from .parser import build_arg_parser
```

Catch `SearchValidationError` instead of `HTTPException`:

```python
except SearchValidationError as exc:
    print(f"CLI failed: {exc.message}", file=sys.stderr)
    return 1
```

- [ ] **Step 6: Replace root `cli.py` with thin entry point**

Root `cli.py` should become:

```python
"""Root command-line entry point for the historical news search engine."""

from __future__ import annotations

from backend.cli.parser import build_api_params, build_arg_parser
from backend.cli.output import format_table
from backend.cli.workflow import main

__all__ = [
    "build_api_params",
    "build_arg_parser",
    "format_table",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Update CLI tests**

In `tests/test_cli.py`, import parser and output helpers from the new modules.

```python
from backend.cli.parser import build_api_params, build_arg_parser
from backend.cli.output import format_table
```

Add a root-entry import smoke test:

```python
class RootCliCompatibilityTests(unittest.TestCase):
    """Check that the historical root CLI module still exports public helpers."""

    def test_root_cli_reexports_public_helpers(self) -> None:
        """Existing imports from cli.py should continue to work."""
        import cli

        self.assertIs(callable(cli.main), True)
        self.assertIs(callable(cli.build_arg_parser), True)
        self.assertIs(callable(cli.build_api_params), True)
        self.assertIs(callable(cli.format_table), True)
```

- [ ] **Step 8: Run CLI tests**

Run:

```bash
uv run python -m unittest tests.test_cli -v
```

Expected:
- CLI parser, API mapping, table formatting, and root import compatibility tests pass.

- [ ] **Step 9: Commit CLI split**

Run:

```bash
git add cli.py backend/cli tests/test_cli.py
git commit -m "refactor: split cli responsibilities"
```

## Task 7: Update Developer Documentation

**Files:**
- Modify: `GUIDE_ROOT.md`
- Modify: `backend/GUIDE_backend.md`
- Modify: `tests/GUIDE_tests.md`
- Modify: `PROJECT_STRUCTURE.md`
- Modify: `README.md`

- [ ] **Step 1: Update root guide**

In `GUIDE_ROOT.md`, update the root file map:

- `cli.py` is now a thin command entry point.
- `backend/cli/` owns parser, fetch, output, and workflow logic.
- The backend now owns framework-independent validation errors.

- [ ] **Step 2: Update backend guide**

In `backend/GUIDE_backend.md`, add `backend/cli/`, `backend/search/errors.py`, and `backend/sources/registry.py` to the folder tree and code reference.

Add this explanation:

```markdown
Validation raises project-owned `SearchValidationError` exceptions. The FastAPI
route layer maps those errors to HTTP 422 responses so the search package can be
tested and reused without importing FastAPI.
```

- [ ] **Step 3: Update tests guide**

In `tests/GUIDE_tests.md`, mention:

- frontend static security checks,
- validation error mapping tests,
- SQLite resource-warning regression coverage,
- CLI package split coverage.

- [ ] **Step 4: Update structure doc and README**

In `PROJECT_STRUCTURE.md`, include:

```text
backend/
├── cli/
│   ├── __init__.py
│   ├── fetch.py
│   ├── output.py
│   ├── parser.py
│   └── workflow.py
```

In `README.md`, keep the same command examples and add one sentence that `cli.py` remains the supported command entry point.

- [ ] **Step 5: Run documentation sanity check**

Run:

```bash
rg -n "backend/cli|SearchValidationError|registry.py|test_frontend_static" README.md GUIDE_ROOT.md backend/GUIDE_backend.md tests/GUIDE_tests.md PROJECT_STRUCTURE.md
```

Expected:
- Each new architecture component appears in the relevant guide files.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md GUIDE_ROOT.md backend/GUIDE_backend.md tests/GUIDE_tests.md PROJECT_STRUCTURE.md
git commit -m "docs: document stabilized architecture"
```

## Task 8: Final Verification And Review

**Files:**
- No planned source edits in this task.

- [ ] **Step 1: Run lint**

Run:

```bash
uv run ruff check .
```

Expected:
- `All checks passed!`

- [ ] **Step 2: Run full tests**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected:
- All tests pass.
- No `ResourceWarning` appears.

- [ ] **Step 3: Exercise touched runtime entry points**

Run the direct CLI path with the always-available GDELT source:

```bash
uv run python cli.py "inflation" -s 2026-01-01 -e 2026-01-02 --sources gdelt --direct --json
```

Expected:
- Command exits with status `0` if GDELT is reachable.
- JSON output includes top-level `results` and `meta`.

If the network or GDELT endpoint is unavailable, run this import and parser smoke check instead:

```bash
uv run python - <<'PY'
from backend.cli.parser import build_arg_parser
parser = build_arg_parser()
args = parser.parse_args(["inflation", "-s", "2026-01-01", "-e", "2026-01-02"])
print(args.query, args.start, args.end)
PY
```

Expected:
- Output is `inflation 2026-01-01 2026-01-02`.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected:
- No uncommitted implementation or documentation changes remain.
- If unrelated user edits existed before implementation, they remain separate and are not included in stabilization commits.

## Self-Review Checklist

- Confirmed bug fixes are covered before architecture refactors.
- Each task is independently testable and committable.
- FastAPI coupling is removed from pure validation logic.
- Runtime state remains process-local but is explicit and bounded.
- Root `cli.py` remains a supported command entry point.
- Guides are updated after behavior and structure changes.
- Full verification includes lint, unit tests, and at least one touched entry point.
