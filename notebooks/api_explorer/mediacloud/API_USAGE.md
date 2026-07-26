# MediaCloud API Usage

Official docs:
- https://www.mediacloud.org/documentation/
- https://mediacloud.readthedocs.io/en/latest/topics/working-with-api.html
- https://github.com/mediacloud/api-client

Authentication:
- Requires `MEDIACLOUD_API_KEY`.
- Active API workflow in this project uses header auth:
  - `Authorization: Token <MEDIACLOUD_API_KEY>`

Environment setup in root `.env`:
- `MEDIACLOUD_API_KEY`
- Optional override:
  - `MEDIACLOUD_BASE_URL` (defaults to `https://search.mediacloud.org/api/search/story-list`)

Story endpoint used in this project:
- `https://search.mediacloud.org/api/search/story-list`

Common parameters:
- `q`: query text (for example, `inflation OR "interest rates"`)
- `start`: start date (`YYYY-MM-DD`)
- `end`: end date (`YYYY-MM-DD`)
- `platform`: defaults to `onlinenews-mediacloud`
- `page_size`: number of stories returned per call

Typical workflow:
1. Set `MEDIACLOUD_API_KEY`.
2. Build a focused query using `q`, `start`, and `end`.
3. Fetch stories and inspect title/url/publish-time fields.
4. Save raw JSON for schema checks.

Direct text note:
- `search/story-list` is primarily a story metadata stream.
- In practice, treat this endpoint as metadata-first; do not assume a stable full-article `text` field in every record.
- The notebook probes returned stories for `text`, `content`, `body`, `description`, and `summary` so you can confirm actual payload behavior for your key/query.

Notebook in this folder:
- `mediacloud_api_explorer.ipynb` previews parameters and runs live fetch only when `MEDIACLOUD_API_KEY` exists.
- The notebook auto-discovers root `.env` by searching upward from the current working directory, so it works from both:
  - workspace root (`/Users/gwh/projects/news`)
  - notebook folder (`notebooks/api_explorer/mediacloud`)
- Live payloads are written to `notebooks/api_explorer/mediacloud/outputs/` on successful requests.
- API keys are never added to request URLs in this v4 flow (header auth only).
- The live cell runs DNS diagnostics for the configured endpoint host before request attempts.
- Legacy v2-style defaults (`rows`, `fq`, `wc`) are auto-converted in the notebook so older saved parameter blocks still execute.

Legacy endpoint note:
- As of March 5, 2026, DNS for `api.mediacloud.org` returned no usable host records in this environment.
- This project therefore defaults to the v4 host `search.mediacloud.org`.
