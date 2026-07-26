"""FastAPI application construction for search and frontend delivery.

The application boundary loads credentials and validated settings once, builds
the process-local cache, and injects those objects into route behavior.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from news.api.models import (
    FrontendConfigResponse,
    SearchResponse,
    SourceStatusResponse,
)
from news.api.params import SearchQueryParams
from news.exports.formats import format_csv, format_json
from news.search import SearchExecutor, run_search
from news.search.cache import SearchResultCache, build_search_cache
from news.search.errors import SearchValidationError
from news.search.models import SearchResult
from news.sources import get_source_status, search_all_detailed
from news.web.config import AppSettings, load_settings
from news.web.paths import CONFIG_ENVIRONMENT_VARIABLE, env_path, static_dir

APP_TITLE = "Historical News Search Engine"
APP_DESCRIPTION = (
    "Search GDELT, MediaCloud, ACLED, The New York Times, The Guardian, "
    "and NewsAPI by keyword and date range."
)
APP_VERSION = "0.1.0"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SourceStatusProvider = Callable[[], list[dict[str, object]]]


def create_app(
    settings: AppSettings,
    *,
    search_cache: SearchResultCache | None = None,
    search_executor: SearchExecutor = search_all_detailed,
    source_status_provider: SourceStatusProvider = get_source_status,
) -> FastAPI:
    """Construct an application from validated runtime dependencies.

    Parameters
    ----------
    settings : AppSettings
        Immutable frontend and cache settings.
    search_cache : SearchResultCache | None, optional
        Cache supplied by a caller or test. ``None`` builds one from settings.
    search_executor : SearchExecutor, optional
        Provider fan-out function. Tests may inject an offline fake.
    source_status_provider : SourceStatusProvider, optional
        Provider metadata function. Tests may inject deterministic status.

    Returns
    -------
    FastAPI
        Fully configured application with routes and packaged static assets.
    """
    active_cache = (
        build_search_cache(settings.cache)
        if search_cache is None
        else search_cache
    )
    static_assets = static_dir()
    application = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
    )
    application.state.settings = settings
    application.state.search_cache = active_cache
    application.mount(
        "/static",
        StaticFiles(directory=str(static_assets)),
        name="static",
    )

    @application.get("/")
    async def index() -> FileResponse:
        """Serve the browser app."""
        return FileResponse(str(static_assets / "index.html"))

    @application.get("/api/config", response_model=FrontendConfigResponse)
    async def config() -> dict[str, object]:
        """Return validated frontend configuration values."""
        return settings.frontend.to_dict()

    @application.get("/api/sources", response_model=list[SourceStatusResponse])
    async def sources() -> list[dict[str, object]]:
        """Return source metadata and availability."""
        return source_status_provider()

    @application.get("/api/search", response_model=SearchResponse)
    async def search(params: SearchQueryParams = Depends()) -> dict[str, object]:
        """Search providers and return the merged article page."""
        result = await _run_search_request(
            params,
            cache=active_cache,
            executor=search_executor,
        )
        return result.to_payload()

    @application.get("/api/export/csv")
    async def export_csv(params: SearchQueryParams = Depends()) -> Response:
        """Export the current provider page as comma-separated values (CSV)."""
        result = await _run_search_request(
            params,
            cache=active_cache,
            executor=search_executor,
        )
        return Response(
            content=format_csv(result.articles),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="news_export.csv"'},
        )

    @application.get("/api/export/json")
    async def export_json(params: SearchQueryParams = Depends()) -> Response:
        """Export the current provider page as JavaScript Object Notation."""
        result = await _run_search_request(
            params,
            cache=active_cache,
            executor=search_executor,
        )
        return Response(
            content=format_json(result.articles),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="news_export.json"'},
        )

    return application


def create_configured_app(
    config_file: Path | str | None = None,
) -> FastAPI:
    """Load local credentials and settings, then construct the application.

    Parameters
    ----------
    config_file : Path | str | None, optional
        Explicit TOML configuration path. ``None`` applies normal resolution.

    Returns
    -------
    FastAPI
        Application configured for the current process.
    """
    load_dotenv(env_path())
    return create_app(load_settings(config_file))


async def _run_search_request(
    params: SearchQueryParams,
    *,
    cache: SearchResultCache,
    executor: SearchExecutor,
) -> SearchResult:
    """Validate request parameters and run the shared search pipeline."""
    try:
        request = params.to_search_request()
    except SearchValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await run_search(request, executor=executor, cache=cache)


app = create_configured_app()


def main(argv: list[str] | None = None) -> None:
    """Start the local FastAPI server.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command arguments. ``None`` reads the process arguments.
    """
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the news search server.")
    parser.add_argument(
        "--config",
        help=(
            "TOML configuration path. Overrides NEWS_CONFIG and the "
            "current-directory config.toml."
        ),
    )
    args = parser.parse_args(argv)
    if args.config:
        os.environ[CONFIG_ENVIRONMENT_VARIABLE] = args.config

    uvicorn.run(
        "news.api.app:create_configured_app",
        factory=True,
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
