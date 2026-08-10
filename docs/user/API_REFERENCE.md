# API reference

Base URL when running locally: `http://127.0.0.1:8000`

## Signing in

Every route below requires the account set through `UI_USERNAME` and
`UI_PASSWORD`. A program sends it as HTTP Basic authentication:

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
