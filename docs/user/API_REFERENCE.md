# API reference

Base URL when running locally: `http://127.0.0.1:8000`

## Signing in

Every route below requires one of the configured accounts. The first is set
through `UI_USERNAME` and `UI_PASSWORD`; the optional second and third use the
numbered settings described in `docs/user/SIGN_IN.md`, and any of them opens
every route. A program sends its account as HTTP Basic authentication:

```bash
curl -u "$UI_USERNAME:$UI_PASSWORD" "http://127.0.0.1:8000/api/config"
```

Without valid credentials the route answers `401` with a JSON `detail`. The
response has no `WWW-Authenticate` header, so a browser shows the application's
own sign-in page rather than a native password box. `GET /healthz` and the files
under `/static` need no account. Full rules are in `docs/user/SIGN_IN.md`.

## Common query parameters

The search and export routes accept the same parameters.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `q` | string | required | Search text |
| `start` | string | required | Start date `YYYY-MM-DD` |
| `end` | string | required | End date `YYYY-MM-DD` |
| `sources` | string | `""` | Comma-separated source names |
| `language` | string | `""` | Language filter |
| `dedupe` | bool | `true` | Remove repeated articles |
| `exact_phrase` | string | `""` | Phrase that must appear |
| `exclude_terms` | string | `""` | Comma-separated terms to exclude |
| `domain` | string | `""` | Domains to include |
| `exclude_domains` | string | `""` | Domains to exclude |
| `search_scope` | string | `all` | `all` or `title` |
| `match_mode` | string | `provider` | `provider`, `all_terms`, or `any_term` |
| `provider_sort` | string | `default` | Source sort mode |
| `section` | string | `""` | Section filters |
| `news_desk` | string | `""` | NYT desk filters |
| `guardian_tag` | string | `""` | Guardian tags |
| `newsapi_search_in` | string | `all` | NewsAPI field scope |
| `sort` | string | `date_desc` | `date_desc` or `date_asc` |
| `page` | integer | `1` | 1-based source page |

Validation rules:

- Dates must use strict `YYYY-MM-DD`.
- `start` must be on or before `end`.
- A date range cannot exceed 366 days.
- An unknown source returns HTTP 422.

## `GET /api/config`

Returns the validated browser settings chosen from an explicit path,
`NEWS_CONFIG`, `config.toml` in the current directory, or packaged defaults.

### Example

```bash
curl "http://127.0.0.1:8000/api/config"
```

### Example response

```json
{
  "default_english_only": true,
  "default_sources": ["guardian", "nyt"]
}
```

## `GET /api/sources`

Returns source availability and descriptions.

### Example

```bash
curl "http://127.0.0.1:8000/api/sources"
```

### Example response

```json
[
  {
    "name": "gdelt",
    "display_name": "GDELT Project",
    "description": "Open global news article index (no auth required)",
    "available": true
  }
]
```

## `GET /api/search`

Runs one validated source-page search and returns normalized articles and
search details.

### Example

```bash
curl "http://127.0.0.1:8000/api/search?q=inflation&start=2025-01-01&end=2025-03-01&sources=guardian,nyt&language=en"
```

### Example response

```json
{
  "results": [
    {
      "title": "Fed holds rates steady",
      "url": "https://example.com/fed",
      "date": "2026-03-20",
      "source": "guardian",
      "domain": "example.com",
      "language": "en",
      "summary": "Officials left the policy rate unchanged.",
      "content": "",
      "section": "Business",
      "author": "Jane Doe",
      "matched_sources": ["guardian"],
      "duplicate_count": 1
    }
  ],
  "meta": {
    "query": "fed",
    "start": "2026-03-01",
    "end": "2026-03-20",
    "language": "en",
    "deduplicate": true,
    "exact_phrase": "",
    "exclude_terms": [],
    "include_domains": [],
    "exclude_domains": [],
    "search_scope": "all",
    "match_mode": "provider",
    "provider_sort": "default",
    "section_filters": [],
    "news_desk_filters": [],
    "guardian_tags": [],
    "newsapi_search_in": "all",
    "sort_order": "date_desc",
    "page": 1,
    "has_more": false,
    "has_previous": false,
    "returned": 1,
    "requested_sources": ["guardian"],
    "total": 1,
    "total_before_deduplication": 1,
    "duplicates_removed": 0,
    "source_reports": [
      {
        "name": "guardian",
        "display_name": "The Guardian",
        "available": true,
        "requested": true,
        "returned": 1,
        "has_more": false,
        "error": ""
      }
    ]
  }
}
```

## `GET /api/export/csv`

Runs the same single-page search as `/api/search` and returns a downloadable
CSV file.

```bash
curl -OJ "http://127.0.0.1:8000/api/export/csv?q=inflation&start=2025-01-01&end=2025-03-01"
```

Response: `text/csv` with an attachment disposition.

## `GET /api/export/json`

Runs the same single-page search as `/api/search` and returns the article list
as a downloadable JSON file.

```bash
curl -OJ "http://127.0.0.1:8000/api/export/json?q=inflation&start=2025-01-01&end=2025-03-01"
```

Response: `application/json` with an attachment disposition and a JSON array of
normalized article objects.

## `GET /api/trends/interest`

Returns how much the public searched for the same keywords during the same
window the article search uses. This is the only Google Trends route: the
project studies past windows, so live "what is popular now" data is out of
scope, and Google has removed those endpoints anyway.

### Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `q` | string | required | The same query used for article search |
| `start` | string | required | Inclusive window start `YYYY-MM-DD` |
| `end` | string | required | Inclusive window end `YYYY-MM-DD` |
| `geo` | string | `""` | Geography code such as `US` or `US-NY`; empty uses `trends.default_geo` |
| `as_of` | string | `""` | Optional decision date inside the window |

`q` is reduced to plain search terms before it reaches Google, which accepts no
operators. Quoted phrases stay whole, `AND`/`OR`/`NOT` are dropped, excluded
terms (`-crypto`) are removed because Trends cannot express exclusion, repeats
are collapsed, and at most five terms are used. So
`"central bank" AND (inflation OR Inflation) -crypto` becomes the two keywords
`central bank` and `inflation`.

### Reading the values

Values are a relative index from 0 to 100, never absolute search counts. 100 is
the highest point on or before `anchor_date` and everything else is scaled
against it, so two series fetched over different windows are not comparable. A
0 can mean the term was below Google's reporting threshold rather than
unsearched. `granularity` reports the point spacing Google chose from the
window length: up to about 7 days gives `hourly`, up to 9 months `daily`, up to
5 years `weekly`, and longer `monthly`.

### Why `as_of` exists

Google divides every value by the peak of the whole requested window, including
days after the one being read. A series fetched for all of 2017 therefore tells
every January value where the May peak sat, which is look-ahead bias arriving
through the scaling rather than through the choice of data. Passing `as_of`
drops points after that date and rescales what remains to the highest value up
to it, giving the scale a researcher standing on that date could have seen.

Measured example for `bitcoin` in the United States: 2017-01-05 reads 100 when
fetched with the window ending 2017-03-31 and 30 when fetched with the window
ending 2017-09-15.

### Example

```bash
curl -u "$UI_USERNAME:$UI_PASSWORD" \
  "http://127.0.0.1:8000/api/trends/interest?q=bitcoin&start=2017-01-01&end=2017-09-15&as_of=2017-01-05&geo=US"
```

```json
{
  "keywords": ["bitcoin"],
  "start_date": "2017-01-01",
  "end_date": "2017-01-05",
  "geo": "US",
  "granularity": "daily",
  "dates": ["2017-01-01", "2017-01-02", "2017-01-03", "2017-01-04", "2017-01-05"],
  "is_partial": [false, false, false, false, false],
  "values": {"bitcoin": [42.86, 78.57, 71.43, 82.14, 100.0]},
  "anchor_date": "2017-01-05",
  "fetched_at": "2026-08-10T23:05:01+00:00"
}
```

### Failures

- HTTP 422 when the query holds no searchable term, the dates are malformed or
  reversed, the start predates Google's 2004 archive, or `as_of` falls outside
  the window.
- HTTP 502 when Google rejects the request, rate limits it (HTTP 429), or the
  network fails. Requests are already spaced by
  `trends.seconds_between_requests`; raise that setting if 502 keeps appearing.

## Error responses

### Validation failure

HTTP 422:

```json
{
  "detail": "Unknown source 'foo'. Allowed values: acled, gdelt, guardian, mediacloud, newsapi, nyt"
}
```

Other common failures are an empty query, invalid date format, reversed dates,
a range longer than 366 days, or an invalid value for `match_mode`,
`search_scope`, `provider_sort`, `sort`, or `newsapi_search_in`.

## OpenAPI definition

The generated OpenAPI schema is checked in at
`docs/reference/openapi.json`. Tests compare it with the current FastAPI
routes and response models, so a public API change must be reviewed explicitly.

Regenerate it after an intentional API change:

```bash
uv run python scripts/generate_openapi.py
```
