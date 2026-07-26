# Common Crawl News Dataset Usage

Official references:
- https://commoncrawl.org/blog/news-dataset-available
- https://commoncrawl.org/get-started
- https://github.com/commoncrawl/cc-pyspark

Dataset access used in this project:
- `https://data.commoncrawl.org/crawl-data/CC-NEWS/YYYY/MM/warc.paths.gz`

What this gives you:
- A gzipped list of WARC file paths for that month of CC-NEWS.
- Each WARC path points to archived news pages that can be downloaded and parsed.
- It does **not** return article JSON rows directly; this endpoint is a file manifest.

How to read a sample path:
- Example: `crawl-data/CC-NEWS/2026/03/CC-NEWS-20260301003313-06997.warc.gz`
- `crawl-data/CC-NEWS`: dataset prefix (Common Crawl News corpus).
- `2026/03`: year and month partition directory.
- `CC-NEWS-20260301003313-06997.warc.gz`:
  - `20260301003313` is a UTC timestamp (`YYYYMMDDhhmmss`) for the crawl segment.
  - `06997` is the shard/segment id in that crawl run.
  - `.warc.gz` is a gzipped WARC (Web ARChive) file containing many captured HTTP records.

To download one listed file, prepend:
- `https://data.commoncrawl.org/`
- Full URL example: `https://data.commoncrawl.org/crawl-data/CC-NEWS/2026/03/CC-NEWS-20260301003313-06997.warc.gz`

Typical workflow:
1. Pick year/month path list (`warc.paths.gz`).
2. Decompress and inspect sample WARC paths.
3. Download specific WARC files for parsing/extraction.
4. Build article-level datasets from parsed WARC content.

Why this can look confusing:
- Seeing only values like `crawl-data/CC-NEWS/2026/03/CC-NEWS-...warc.gz` is expected.
- Those are object keys inside Common Crawl storage, not final article objects.
- Convert each key to a downloadable URL by prefixing `https://data.commoncrawl.org/`.
- The notebook now prints one full WARC URL example so this mapping is explicit.

Notebook in this folder:
- `commoncrawl_api_explorer.ipynb` fetches one monthly `warc.paths.gz`, prints sample paths, prints one full WARC URL example, and saves a sample JSON payload to `outputs/commoncrawl_live_paths_sample.json`.
- It also generates two cc-pyspark-ready manifest files:
  - `outputs/cc_news_manifest_relative.txt` (relative object keys)
  - `outputs/cc_news_manifest_https.txt` (full HTTPS URLs)
- The notebook prints `spark-submit` command patterns aligned with `commoncrawl/cc-pyspark` usage (`input` manifest + optional `--input_base_url https://data.commoncrawl.org/`).
