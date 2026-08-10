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
