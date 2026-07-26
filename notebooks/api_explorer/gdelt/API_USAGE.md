# GDELT API Usage

Official docs:
- https://www.gdeltproject.org/#downloading

Document API endpoint:
- `https://api.gdeltproject.org/api/v2/doc/doc`

Common parameters:
- `query`: keyword/boolean query
- `mode`: `ArtList`, `TimelineVol`, `TimelineTone`, etc.
- `format`: `json`
- `maxrecords`: number of rows
- `sort`: `DateDesc` or other sort mode

Typical workflow:
1. Start with a small query and `maxrecords`.
2. Fetch `ArtList` to inspect article-level output.
3. Expand with timeline modes for aggregate signals.
4. Handle `429` with retry/backoff.

Notebook in this folder:
- `gdelt_api_explorer.ipynb` includes a live-fetch cell that prints article titles/URLs and saves a raw JSON payload to `outputs/gdelt_live_response.json`.
