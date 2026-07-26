"""FastAPI application for search, export, and frontend delivery.

The module wires HTTP routes to the validated package search pipeline and keeps
request parsing, config reads, and response serialization in one place.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

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
from news.search import run_search
from news.search.errors import SearchValidationError
from news.sources import get_source_status
from news.web.config import read_frontend_config
from news.web.paths import CONFIG_ENVIRONMENT_VARIABLE, env_path, static_dir

load_dotenv(env_path())
STATIC_DIR = static_dir()

app = FastAPI(
    title="Historical News Search Engine",
    description=(
        "Search GDELT, MediaCloud, ACLED, The New York Times, and "
        "The Guardian, and NewsAPI by keyword and date range."
    ),
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    """Serve the browser app."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/config", response_model=FrontendConfigResponse)
async def config() -> dict[str, Any]:
    """Return frontend configuration values."""
    return read_frontend_config()


@app.get("/api/sources", response_model=list[SourceStatusResponse])
async def sources() -> list[dict[str, Any]]:
    """Return source metadata and availability."""
    return get_source_status()


@app.get("/api/search", response_model=SearchResponse)
async def search(params: SearchQueryParams = Depends()) -> dict[str, Any]:
    """Search providers and return the merged article page."""
    result = await _run_search_request(params)
    return result.to_payload()


@app.get("/api/export/csv")
async def export_csv(params: SearchQueryParams = Depends()) -> Response:
    """Export the current provider page as CSV."""
    result = await _run_search_request(params)
    return Response(
        content=format_csv(result.articles),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="news_export.csv"'},
    )


@app.get("/api/export/json")
async def export_json(params: SearchQueryParams = Depends()) -> Response:
    """Export the current provider page as JSON."""
    result = await _run_search_request(params)
    return Response(
        content=format_json(result.articles),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="news_export.json"'},
    )


async def _run_search_request(params: SearchQueryParams):
    """Validate request parameters and run the shared search pipeline."""
    try:
        request = params.to_search_request()
    except SearchValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return await run_search(request)


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
        "news.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
