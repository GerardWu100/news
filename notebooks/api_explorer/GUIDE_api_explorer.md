# GUIDE_api_explorer

## Part 1 - Conceptual Explanation (What, How, Why)

### Purpose and problem statement

`notebooks/api_explorer/` is the source reconnaissance workspace for four news providers:
- ACLED
- GDELT
- MediaCloud
- Common Crawl News

The folder uses a notebook-first setup. Each source subfolder contains:
1. `API_USAGE.md` with official documentation links and usage notes.
2. One notebook that previews parameters and runs optional live fetch.

ACLED also uses two focused helper scripts in the project `scripts/` folder:
- `scripts/acled_oauth_token.py`
- `scripts/acled_bearer_read.py`

### Spine of the logic

1. Read `API_USAGE.md` for endpoint/auth/query conventions.
2. Open the source notebook.
3. Run preview cell to inspect capabilities and default query shape.
4. Run live cell to fetch real output when credentials/network allow.
5. Save raw payload in `outputs/` for schema inspection.

### Output behavior

- GDELT and Common Crawl notebook live cells currently produce saved artifacts in `outputs/`.
- ACLED and MediaCloud require credentials, so live cells print clear setup messages when keys are missing.
- ACLED and MediaCloud notebooks auto-discover root `.env` even when launched from repository root.
- MediaCloud notebook uses the v4 `search/story-list` endpoint, authenticates with `Authorization: Token ...`, runs DNS diagnostics, auto-converts legacy v2 parameter shapes (`rows`/`fq`) to v4 date params, and reports whether optional text-bearing fields appear in returned stories.
- Common Crawl notebook explicitly distinguishes manifest paths from article-level records and prints a full WARC URL example.
- Common Crawl notebook also exports cc-pyspark-ready manifests and prints Spark command templates for downstream large-scale extraction jobs.

### Inputs, outputs, assumptions

- Inputs:
  - Environment variables loaded from root `.env` (`MEDIACLOUD_API_KEY`, `ACLED_OAUTH_TOKEN_URL`, `ACLED_OAUTH_GRANT_TYPE`, `ACLED_OAUTH_CLIENT_ID`, `ACLED_USERNAME`, `ACLED_PASSWORD`).
  - Query parameters defined inside each notebook.
- Outputs:
  - Source-local JSON artifacts in each provider's `outputs/` folder.
- Assumptions:
  - Source endpoints remain available.
  - User intentionally runs live cells when they want network calls.

## Part 2 - Folder Tree and File Map

```text
notebooks/api_explorer/
├── GUIDE_api_explorer.md
├── acled/
├── gdelt/
├── mediacloud/
└── commoncrawl/
```

- `acled/`, `gdelt/`, `mediacloud/`, `commoncrawl/`: source-isolated folders with one notebook, one API usage guide, and `outputs/`.

## Part 3 - Code Reference (Names and Structure)

- `acled/API_USAGE.md`: ACLED auth + endpoint usage notes.
- `scripts/acled_oauth_token.py`: ACLED OAuth token retrieval and bearer persistence helper.
- `scripts/acled_bearer_read.py`: ACLED bearer-auth data read helper with refresh fallback.
- `acled/acled_api_explorer.ipynb`: ACLED preview and live bearer-read notebook.
- `gdelt/API_USAGE.md`: GDELT parameter and mode notes.
- `gdelt/gdelt_api_explorer.ipynb`: GDELT live-fetch notebook that prints titles/URLs.
- `mediacloud/API_USAGE.md`: MediaCloud auth and story endpoint notes.
- `mediacloud/mediacloud_api_explorer.ipynb`: MediaCloud preview + credential-gated live-fetch notebook.
- `commoncrawl/API_USAGE.md`: CC-NEWS access notes.
- `commoncrawl/commoncrawl_api_explorer.ipynb`: CC-NEWS WARC-manifest live-fetch notebook with a cc-pyspark bridge cell (manifest export + Spark command templates).

Relationship to overall project:
- This folder is the API capability and schema-discovery stage for the news search engine.
