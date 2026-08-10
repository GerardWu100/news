# GUIDE_news

## Purpose

The `news` package implements historical news retrieval from several sources.

## Subpackages

- `api/`: FastAPI app, route models, query parameter parsing, sign-in routes,
  and the check that closes every data route.
- `search/`: validation, shared date handling, cache, filters, duplicate
  removal, sorting, and search details.
- `sources/`: source registry, parallel requests, retries, source adapters, and
  reusable ACLED OAuth setup.
- `exports/`: CSV, JSON, and SQLite writers.
- `cli/`: command parser, fetch paths, table/JSON/JSONL output, and command flow.
- `web/`: installed browser files, packaged defaults, settings-path helpers,
  validated settings, password hashing, stored sign-in state, and
  request-security helpers.

## Sign-in

`web/passwords.py` holds the PBKDF2 hashing and the constant-time check.
`web/credentials.py` turns `UI_USERNAME` and `UI_PASSWORD` into
`.ui_credentials.json` on every startup and re-verifies the stored hash, so no
hashing command exists. `web/auth_store.py` keeps remembered sessions and
failed-attempt counters in locked, atomically replaced JSON files, and
`web/security.py` decides response headers, the client address, and whether the
connection used HTTPS.

Sessions are never cached in memory. Every check reads the session file under
its lock through `AuthStore`, and every change is one locked read-modify-write.
That costs a small file read per signed-in request and buys correctness when
more than one process serves the application: a browser that signs in through
one worker is recognized by all of them. The sign-out token lives in the
session record for the same reason, so the page that shows the button and the
request that submits it need not reach the same process.

`web/security.py` also decides when proxy headers may be believed.
`trust_forwarded_headers` alone is not enough: the machine that opened the
connection must also be on the loopback interface or a private network, which
is where a reverse proxy in front of this server lives. Without that second
condition, any caller could send `X-Forwarded-For` and spend another caller's
failed-attempt budget.

`api/auth.py` holds the runtime state and the routes. `LoginSessions` owns
form tokens, failure counting, and the short-lived cache of accepted HTTP Basic
headers, which exists because hashing is deliberately slow. That cache is
emptied when the account file's modification time changes, so a header accepted
under the old password stops working as soon as the password does. Both the
pending form tokens and the failed-attempt file are bounded, because callers
who have proved nothing yet can add to either.

`require_signed_in` is the dependency attached to every data route;
`request_is_signed_in` is the same check without the exception, used by the
root route so a signed-out browser is redirected rather than refused.
`api/login_page.py` renders the one server-built page, because the rest of the
browser client is static and cannot carry a server-issued token.

## Browser protection headers

`api/app.py` attaches protection headers in a middleware rather than route by
route, so a route added later cannot quietly serve data without them. Routes
that need a wider policy set their own first, and the middleware fills in only
what is missing. Three policies exist because the responses load different
things: the search page needs its own scripts and the linked web fonts, the
sign-in page needs only its inline stylesheet, and JSON, CSV, and redirect
responses need nothing at all. Neither page allows inline scripts or inline
styles, so the browser code sets the result-card animation delay through the
style property rather than through a `style` attribute in the markup.

The factory accepts a `LoginSessions`, so tests point sign-in state at a
temporary directory instead of the operator's data directory.

## Runtime Flow

Browser and CLI inputs become validated search requests. The search service
queries selected sources, applies local filters and optional duplicate removal,
sorts the final page, and returns normalized articles plus search details.
The browser displays the inclusive date boundary and can download the visible
page. The CLI emits full search details in JSON or streams compact article-only
JSONL for later model work.
The API application owns the process-local cache and passes it into the search
service; low-level search modules do not read configuration files.

Two callers asking the identical question at the same moment share one round of
provider requests rather than each spending the rate limits. The search service
keeps the running searches in a small mapping keyed by the validated request; a
later caller waits on the search already in flight and receives its own copy of
the result. A caller that gives up does not cancel the search the others are
still waiting on. This matters because a reloaded browser page, or two commands
started together, produce exactly this overlap.

The application factory also accepts a provider executor and source-status
function. Production uses the registered adapters; tests supply offline fakes
without patching module globals.

Importing the API module does not construct a configured application.
`news-server` parses command arguments first, then the server invokes the
factory. This preserves the documented rule that `--config` takes precedence
even when a current-directory `config.toml` is invalid. The command also owns
the host, port, and development-only reload settings required by local and
container runtimes.

Before parsing CLI arguments, `news-search` loads the root `.env`. Its
`--server` value therefore defaults to `NEWS_SERVER_URL` when configured and
otherwise uses `http://localhost:8000`. An explicit `--server` remains the
one-call override. This keeps the same structured retrieval workflow usable
against a local process, Docker Compose service, or protected remote server.

## Public Imports

- `news.search` exports validated request/result types, the executor type, the
  request builder, search runner, and deduplication entry points.
- `news.sources` exports shared source models and parallel-search entry points,
  not individual adapters.
- `news.exports` exports CSV, JSON, and SQLite format functions.
- Root, API, CLI, and web package initializers intentionally export nothing;
  callers use explicit module paths for those boundaries.
