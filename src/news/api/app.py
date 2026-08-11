"""Build the FastAPI application and serve the browser client.

The application loads credentials and validated settings once, creates the
process-local cache, and passes those objects to the route functions.

Everything that returns news data requires a signed-in account. The sign-in
page, the browser's own static files, and the health check stay open, because
none of them expose search results.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from news.api.auth import (
    LOGIN_PATH,
    LoginSessions,
    build_auth_router,
    request_is_signed_in,
    require_signed_in,
)
from news.api.models import (
    FrontendConfigResponse,
    SearchResponse,
    SourceStatusResponse,
    TrendsInterestResponse,
)
from news.api.params import SearchQueryParams
from news.api.trends_params import TrendsQueryParams
from news.exports.formats import format_csv, format_json
from news.search import SearchExecutor, run_search
from news.search.cache import SearchResultCache, build_search_cache
from news.search.errors import SearchValidationError
from news.search.models import SearchResult
from news.sources import get_source_status, search_all_detailed
from news.trends.google import GoogleTrendsClient
from news.trends.keywords import keywords_from_query
from news.trends.models import (
    InterestOverTime,
    TrendsClient,
    TrendsFetchError,
    TrendsValidationError,
)
from news.trends.rebase import rebase_as_of
from news.web.auth_store import AuthStore
from news.web.config import AppSettings, load_settings
from news.web.credentials import sync_ui_credentials
from news.web.paths import (
    CONFIG_ENVIRONMENT_VARIABLE,
    credentials_path,
    data_dir,
    env_path,
    login_state_path,
    session_state_path,
    static_dir,
)
from news.web.security import (
    data_response_headers,
    request_is_secure,
    search_page_headers,
    static_asset_headers,
)

APP_TITLE = "Historical News Search Engine"
APP_DESCRIPTION = (
    "Search GDELT, MediaCloud, ACLED, The New York Times, The Guardian, "
    "and NewsAPI by keyword and date range."
)
APP_VERSION = "0.1.0"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
STATIC_URL_PREFIX = "/static"
SourceStatusProvider = Callable[[], list[dict[str, object]]]

_logger = logging.getLogger("news.api.app")


def create_app(
    settings: AppSettings,
    *,
    search_cache: SearchResultCache | None = None,
    search_executor: SearchExecutor = search_all_detailed,
    source_status_provider: SourceStatusProvider = get_source_status,
    login_sessions: LoginSessions | None = None,
    trends_client: TrendsClient | None = None,
) -> FastAPI:
    """Build an application from validated settings and supplied dependencies.

    Parameters
    ----------
    settings : AppSettings
        Validated browser, cache, and security settings.
    search_cache : SearchResultCache | None, optional
        Cache supplied by a caller or test. ``None`` builds one from the settings.
    search_executor : SearchExecutor, optional
        Function that queries sources. Tests may supply an offline fake.
    source_status_provider : SourceStatusProvider, optional
        Function that reports source status. Tests may supply deterministic data.
    login_sessions : LoginSessions | None, optional
        Sign-in state supplied by a caller or test. ``None`` reads the account
        and session files from the data directory.
    trends_client : TrendsClient | None, optional
        Google Trends source supplied by a caller or test. ``None`` builds the
        live client with the configured gap between requests.

    Returns
    -------
    FastAPI
        Application with routes and packaged browser files.
    """
    active_cache = (
        build_search_cache(settings.cache) if search_cache is None else search_cache
    )
    active_sessions = (
        _build_login_sessions(settings) if login_sessions is None else login_sessions
    )
    # One client per application, so its request pacer is shared by every
    # browser request instead of each one starting its own gap.
    active_trends_client = (
        GoogleTrendsClient(
            seconds_between_requests=settings.trends.seconds_between_requests
        )
        if trends_client is None
        else trends_client
    )
    static_assets = static_dir()
    # The interactive documentation and schema routes are switched off because
    # they answer without a session and would list every route and parameter to
    # anyone who reaches the port. The schema itself is still available offline
    # through ``application.openapi()``, which is how the checked-in contract in
    # docs/reference/openapi.json is generated and tested.
    application = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    application.state.settings = settings
    application.state.search_cache = active_cache
    application.state.login_sessions = active_sessions
    application.state.trends_client = active_trends_client
    application.mount(
        "/static",
        StaticFiles(directory=str(static_assets)),
        name="static",
    )
    application.include_router(build_auth_router())

    @application.middleware("http")
    async def apply_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Attach browser-protection headers to every response.

        Routes that need a wider Content Security Policy, such as the search
        page and the sign-in page, set their own before this runs; only the
        headers a response does not already carry are filled in here. That way
        no route can be added later that quietly serves data without them.
        """
        response = await call_next(request)
        connection_is_secure = request_is_secure(
            request,
            settings.security.trust_forwarded_headers,
        )
        if request.url.path.startswith(STATIC_URL_PREFIX):
            headers = static_asset_headers(connection_is_secure=connection_is_secure)
        else:
            headers = data_response_headers(connection_is_secure=connection_is_secure)

        for header_name, header_value in headers.items():
            response.headers.setdefault(header_name, header_value)
        return response

    @application.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Report that the process is serving, without exposing any data."""
        return {"status": "ok"}

    @application.get("/", include_in_schema=False)
    async def index(request: Request) -> Response:
        """Serve the browser app, or the sign-in page when signed out."""
        if not request_is_signed_in(request):
            return RedirectResponse(url=LOGIN_PATH, status_code=302)
        return FileResponse(
            str(static_assets / "index.html"),
            headers=search_page_headers(
                connection_is_secure=request_is_secure(
                    request,
                    settings.security.trust_forwarded_headers,
                )
            ),
        )

    @application.get(
        "/api/config",
        response_model=FrontendConfigResponse,
        dependencies=[Depends(require_signed_in)],
    )
    async def config() -> dict[str, object]:
        """Return the validated browser settings."""
        return settings.frontend.to_dict()

    @application.get(
        "/api/sources",
        response_model=list[SourceStatusResponse],
        dependencies=[Depends(require_signed_in)],
    )
    async def sources() -> list[dict[str, object]]:
        """Return source descriptions and availability."""
        return source_status_provider()

    @application.get(
        "/api/search",
        response_model=SearchResponse,
        dependencies=[Depends(require_signed_in)],
    )
    async def search(params: SearchQueryParams = Depends()) -> dict[str, object]:
        """Search the selected sources and return one merged page."""
        result = await _run_search_request(
            params,
            cache=active_cache,
            executor=search_executor,
        )
        return result.to_payload()

    @application.get(
        "/api/export/csv",
        dependencies=[Depends(require_signed_in)],
    )
    async def export_csv(params: SearchQueryParams = Depends()) -> Response:
        """Download the current source page as comma-separated values (CSV)."""
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

    @application.get(
        "/api/export/json",
        dependencies=[Depends(require_signed_in)],
    )
    async def export_json(params: SearchQueryParams = Depends()) -> Response:
        """Download the current source page as JavaScript Object Notation (JSON)."""
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

    @application.get(
        "/api/trends/interest",
        response_model=TrendsInterestResponse,
        dependencies=[Depends(require_signed_in)],
    )
    def trends_interest(params: TrendsQueryParams = Depends()) -> dict[str, object]:
        """Return search attention for the same keywords and window as a search.

        Declared as a plain function rather than an async one on purpose. The
        Google Trends library blocks on HTTP and also sleeps to space requests
        out, so FastAPI runs this in its worker thread pool and the event loop
        stays free for article searches.
        """
        return _run_trends_request(
            params,
            client=active_trends_client,
            default_geo=settings.trends.default_geo,
        ).to_dict()

    return application


def _run_trends_request(
    params: TrendsQueryParams,
    *,
    client: TrendsClient,
    default_geo: str,
) -> InterestOverTime:
    """Validate trends parameters, fetch the series, and rebase when asked.

    Errors are mapped by whose fault they are: a bad query, window, or
    as-of date is the caller's and returns HTTP 422, while a Google outage or
    rate limit is upstream and returns HTTP 502.
    """
    try:
        keywords = keywords_from_query(params.q)
        series = client.interest_over_time(
            list(keywords),
            start_date=params.start,
            end_date=params.end,
            geo=params.geo.strip() or default_geo,
        )
        if params.as_of.strip():
            series = rebase_as_of(series, params.as_of.strip())
    except TrendsValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except TrendsFetchError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
    return series


def _build_login_sessions(settings: AppSettings) -> LoginSessions:
    """Create sign-in state backed by the data-directory state files."""
    return LoginSessions(
        AuthStore(
            session_file=session_state_path(),
            login_state_file=login_state_path(),
        ),
        credentials_file=credentials_path(),
        trust_forwarded_headers=settings.security.trust_forwarded_headers,
    )


def create_configured_app(
    config_file: Path | str | None = None,
) -> FastAPI:
    """Load local credentials and settings, then construct the application.

    Reads ``.env`` from the data directory, refreshes the stored password hash
    of every configured sign-in account (``UI_USERNAME`` and ``UI_PASSWORD``,
    plus the numbered slots described in :mod:`news.web.credentials`), and logs
    the result. Settings without a single complete account leave every
    protected route closed rather than open.

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
    _logger.info("%s", sync_ui_credentials(data_dir()))
    return create_app(load_settings(config_file))


async def _run_search_request(
    params: SearchQueryParams,
    *,
    cache: SearchResultCache,
    executor: SearchExecutor,
) -> SearchResult:
    """Validate request parameters and run the common search process."""
    try:
        request = params.to_search_request()
    except SearchValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await run_search(request, executor=executor, cache=cache)


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
            "TOML settings path. Overrides NEWS_CONFIG and the "
            "current-directory config.toml."
        ),
    )
    parser.add_argument(
        "--host",
        default=SERVER_HOST,
        help=f"Interface on which to listen (default: {SERVER_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SERVER_PORT,
        help=f"TCP port on which to listen (default: {SERVER_PORT})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the development server when source files change",
    )
    args = parser.parse_args(argv)
    if args.config:
        os.environ[CONFIG_ENVIRONMENT_VARIABLE] = args.config

    # Give the root logger a handler so the credential status line written
    # while the application is built reaches the terminal alongside uvicorn's
    # own output.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    uvicorn.run(
        "news.api.app:create_configured_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
