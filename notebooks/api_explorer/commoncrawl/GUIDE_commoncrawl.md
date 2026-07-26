# GUIDE_commoncrawl

## Part 1 - Conceptual Explanation (What, How, Why)

### Purpose

This folder explores Common Crawl News dataset access via monthly `warc.paths.gz` manifests.

### Logic spine

1. Read `API_USAGE.md` for dataset links and usage pattern.
2. Run preview cell for dataset context.
3. Run live cell to download one monthly `warc.paths.gz` manifest.
4. Decompress and print sample WARC paths.
5. Print one full WARC URL example (`https://data.commoncrawl.org/<path>`).
6. Save sampled payload to `outputs/commoncrawl_live_paths_sample.json`.
7. Generate cc-pyspark input manifests (`relative` and `https` variants).
8. Print cc-pyspark `spark-submit` command patterns for downstream extraction jobs.

Path anatomy used by the live output:
- A sample path such as `crawl-data/CC-NEWS/2026/03/CC-NEWS-20260301003313-06997.warc.gz` is a relative object key inside Common Crawl storage.
- Prefix it with `https://data.commoncrawl.org/` to get the direct download URL.
- Filename timestamp (`20260301003313`) is UTC crawl-segment time; trailing number (`06997`) is shard id.

### Inputs/outputs and invariants

- Inputs: monthly manifest URL configured in notebook.
- Outputs: `outputs/commoncrawl_live_paths_sample.json`.
- Outputs: `outputs/cc_news_manifest_relative.txt` and `outputs/cc_news_manifest_https.txt` for Spark workflows.
- Invariant: `warc.paths.gz` is treated as a manifest (path list), not as an article JSON API response.
- Invariant: the notebook prints an explicit note that article-level extraction requires WARC parsing.
- Invariant: cc-pyspark bridge cell does not assume local Spark install; it only writes manifests and prints command templates.
- Invariant: live cell reports failure reasons when endpoint/network is unavailable.

## Part 2 - Folder Tree and File Map

```text
commoncrawl/
├── GUIDE_commoncrawl.md
├── API_USAGE.md
├── commoncrawl_api_explorer.ipynb
└── outputs/
    ├── .gitkeep
    ├── cc_news_manifest_relative.txt
    ├── cc_news_manifest_https.txt
    └── commoncrawl_live_paths_sample.json
```

- `API_USAGE.md`: official links and usage notes.
- `commoncrawl_api_explorer.ipynb`: preview + live-fetch notebook + cc-pyspark bridge cell.
- `outputs/commoncrawl_live_paths_sample.json`: saved sample of monthly WARC paths.
- `outputs/cc_news_manifest_relative.txt`: line-delimited CC-NEWS object keys for tools that support `--input_base_url`.
- `outputs/cc_news_manifest_https.txt`: line-delimited full HTTPS URLs for direct fetch input.

## Part 3 - Code Reference (Names and Structure)

- Notebook cell 1: dataset context, dynamic current-month manifest URL preview, and explicit manifest-vs-article note.
- Notebook cell 2: live manifest download, decompression, sample extraction, first full WARC URL construction, persistence.
- Notebook cell 3: cc-pyspark bridge - writes manifest files and prints Spark command templates based on `commoncrawl/cc-pyspark` patterns.

How to run:
- Open and run notebook cells in `commoncrawl_api_explorer.ipynb`.
