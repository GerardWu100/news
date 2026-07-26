# GUIDE_mediacloud

## Part 1 - Conceptual Explanation (What, How, Why)

### Purpose

This folder documents and explores MediaCloud story API usage via the active v4 Search API story-list endpoint.

### Logic spine

1. Read `API_USAGE.md` for auth + endpoint conventions.
2. Run preview cell for capabilities and default query parameters.
3. Review the notebook's direct-text expectations before live fetch (`metadata-first`, probe optional text fields).
4. Run live cell to fetch stories when `MEDIACLOUD_API_KEY` is set (`Authorization: Token ...`).
5. Save payload to `outputs/mediacloud_live_response.json` when fetch succeeds.

### Inputs/outputs and invariants

- Inputs: `MEDIACLOUD_API_KEY`, notebook query parameters.
- Outputs: optional `outputs/mediacloud_live_response.json`.
- Invariant: when key is missing, notebook prints explicit credential message.
- Invariant: notebook defaults to `https://search.mediacloud.org/api/search/story-list`.
- Invariant: notebook authenticates with `Authorization: Token <MEDIACLOUD_API_KEY>` and does not place secrets in query strings.
- Invariant: notebook prints DNS diagnostics for the active endpoint host before attempting live fetch.
- Invariant: live cell reports counts of optional text-bearing fields (`text`, `content`, `body`, `description`, `summary`) in returned story objects.
- Invariant: notebook live cell can load root `.env` when launched from repository root or from `notebooks/api_explorer/mediacloud`.
- Invariant: live cell auto-converts legacy v2-style defaults (`rows`, `fq`, `wc`) into v4 parameters (`page_size`, `start`, `end`) for backward compatibility.

## Part 2 - Folder Tree and File Map

```text
mediacloud/
├── GUIDE_mediacloud.md
├── API_USAGE.md
├── mediacloud_api_explorer.ipynb
└── outputs/
    ├── .gitkeep
    └── mediacloud_live_response.json
```

- `API_USAGE.md`: official docs and usage notes.
- `mediacloud_api_explorer.ipynb`: preview + live-fetch notebook.
- `outputs/`: live payload storage.
- `outputs/mediacloud_live_response.json`: latest saved raw response from a successful live notebook run.

## Part 3 - Code Reference (Names and Structure)

- Notebook cell 1: capability and query preview.
- Notebook cell 2: credential-gated live fetch against `search/story-list`, root `.env` auto-discovery, DNS check, legacy-param conversion, optional text-field detection, URL logging without secrets, and payload persistence to `notebooks/api_explorer/mediacloud/outputs/`.

How to run:
- Open and run notebook cells in `mediacloud_api_explorer.ipynb`.
