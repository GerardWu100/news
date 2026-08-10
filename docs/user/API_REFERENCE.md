# API Reference

Base URL when running locally: `http://127.0.0.1:8000`

## Common Query Parameters

The search and export endpoints share the same request shape.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `q` | string | required | Query string |
| `start` | string | required | Start date `YYYY-MM-DD` |
| `end` | string | required | End date `YYYY-MM-DD` |
| `sources` | string | `""` | Comma-separated source names |
| `language` | string | `""` | Language filter |
| `dedupe` | bool | `true` | Enable deduplication |
| `exact_phrase` | string | `""` | Exact phrase requirement |
| `exclude_terms` | string | `""` | Comma-separated exclusion terms |
| `domain` | string | `""` | Include domains |
| `exclude_domains` | string | `""` | Exclude domains |
| `search_scope` | string | `all` | `all` or `title` |
| `match_mode` | string | `provider` | `provider`, `all_terms`, or `any_term` |
| `provider_sort` | string | `default` | Upstream sort mode |
| `section` | string | `""` | Section filters |
| `news_desk` | string | `""` | NYT desk filters |
| `guardian_tag` | string | `""` | Guardian tags |
| `newsapi_search_in` | string | `all` | NewsAPI field scope |
| `sort` | string | `date_desc` | `date_desc` or `date_asc` |
| `page` | integer | `1` | 1-based provider page |

Validation notes:

- dates must use strict `YYYY-MM-DD`
- `start` must be on or before `end`
- date range cannot exceed 366 days
- unknown source names return HTTP 422

## `GET /api/config`

Returns the validated frontend settings resolved from an explicit path,
`NEWS_CONFIG`, current-directory `config.toml`, or packaged defaults.

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

Returns provider availability and descriptions.

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

Runs one validated provider-page search and returns normalized articles plus metadata.

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

Runs the same single-page search as `/api/search` and returns a downloadable CSV file.

### Example

```bash
curl -OJ "http://127.0.0.1:8000/api/export/csv?q=inflation&start=2025-01-01&end=2025-03-01"
```

### Response

- content type: `text/csv`
- content disposition: attachment

## `GET /api/export/json`

Runs the same single-page search as `/api/search` and returns the raw article array as a downloadable JSON file.

### Example

```bash
curl -OJ "http://127.0.0.1:8000/api/export/json?q=inflation&start=2025-01-01&end=2025-03-01"
```

### Response

- content type: `application/json`
- content disposition: attachment
- body: JSON array of normalized article objects

## Google Trends Endpoints

These endpoints return Google's relative search-interest data, not articles.
Every value is a 0-100 index scaled to the highest interest within the
requested window and keyword set; absolute search counts are never available.
Data comes from an unofficial upstream endpoint that rate limits aggressively,
so a burst of requests can return HTTP 502 with a rate-limit message.

Shared query parameters:

| Name | Type | Default | Meaning |
|---|---|---|---|
| `q` | string | required | Comma-separated keywords (max 5; `related` takes exactly 1) |
| `timeframe` | string | `today 12-m` | Google window expression, for example `today 3-m`, `today 5-y`, or `2025-01-01 2025-06-30` |
| `geo` | string | `""` | Geography code (`""` worldwide, `US` country, `US-NY` state) |

## `GET /api/trends/interest`

Returns the search-interest time series. Google picks the granularity from the
window length: roughly daily under nine months, weekly under five years,
monthly beyond that. `is_partial` aligns with `dates` and flags
still-accumulating periods whose values will change.

### Example

```bash
curl "http://127.0.0.1:8000/api/trends/interest?q=bitcoin,ethereum&timeframe=today%203-m&geo=US"
```

### Example response

```json
{
  "keywords": ["bitcoin", "ethereum"],
  "timeframe": "today 3-m",
  "geo": "US",
  "dates": ["2026-08-01", "2026-08-02"],
  "is_partial": [false, true],
  "values": {"bitcoin": [40, 60], "ethereum": [8, 9]},
  "fetched_at": "2026-08-09T12:00:00+00:00"
}
```

## `GET /api/trends/regions`

Returns the regional interest breakdown. The extra `resolution` parameter
accepts `COUNTRY` (default), `REGION` (state/province), `CITY`, or `DMA`
(United States metro areas). Regions with too little volume are omitted.

### Example

```bash
curl "http://127.0.0.1:8000/api/trends/regions?q=bitcoin&geo=US&resolution=REGION"
```

### Example response

```json
{
  "keywords": ["bitcoin"],
  "timeframe": "today 12-m",
  "geo": "US",
  "resolution": "REGION",
  "regions": [{"region": "New York", "values": {"bitcoin": 100}}],
  "fetched_at": "2026-08-09T12:00:00+00:00"
}
```

## `GET /api/trends/related`

Returns queries Google associates with one keyword. In the `top` list `value`
is the 0-100 relative volume index; in the `rising` list it is percent growth
against the prior period, where extreme growth appears as a very large number
(shown as "Breakout" on the Google Trends website).

### Example

```bash
curl "http://127.0.0.1:8000/api/trends/related?q=bitcoin&timeframe=today%203-m"
```

### Example response

```json
{
  "keyword": "bitcoin",
  "timeframe": "today 3-m",
  "geo": "",
  "top": [{"query": "bitcoin price", "value": 100}],
  "rising": [{"query": "bitcoin etf", "value": 250}],
  "fetched_at": "2026-08-09T12:00:00+00:00"
}
```

Trends error mapping: invalid inputs (empty keywords, more than five keywords,
bad `resolution`) return HTTP 422; upstream Google failures, including rate
limits, return HTTP 502.

## Error Responses

### Validation failure

HTTP 422:

```json
{
  "detail": "Unknown source 'foo'. Allowed values: acled, gdelt, guardian, mediacloud, newsapi, nyt"
}
```

Other common validation failures:

- empty query
- invalid date format
- reversed date range
- date range longer than 366 days
- invalid enum value for `match_mode`, `search_scope`, `provider_sort`, `sort`, or `newsapi_search_in`

## OpenAPI Contract

The generated OpenAPI schema is checked in at
`docs/reference/openapi.json`. Tests compare it with the current FastAPI routes
and response models so a public contract change must be reviewed explicitly.

Regenerate it after an intentional API change:

```bash
uv run python scripts/generate_openapi.py
```
