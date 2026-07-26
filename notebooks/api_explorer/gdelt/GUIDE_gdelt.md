# GUIDE_gdelt

## Part 1 - Conceptual Explanation (What, How, Why)

### Purpose

This folder explores GDELT for live article retrieval and schema inspection.

### Logic spine

1. Read `API_USAGE.md` for endpoint/mode/parameter conventions.
2. Run notebook preview cell for capabilities and URL shape.
3. Run notebook live cell to fetch article list.
4. Handle HTTP 429 with retry/backoff.
5. Save raw payload to `outputs/gdelt_live_response.json`.

### Inputs/outputs and invariants

- Inputs: notebook query parameters.
- Outputs: `outputs/gdelt_live_response.json`.
- Invariant: live cell prints clear error state when rate-limited or unavailable.

## Part 2 - Folder Tree and File Map

```text
gdelt/
├── GUIDE_gdelt.md
├── API_USAGE.md
├── gdelt_api_explorer.ipynb
└── outputs/
    ├── .gitkeep
    └── gdelt_live_response.json
```

- `API_USAGE.md`: official doc link and usage notes.
- `gdelt_api_explorer.ipynb`: preview + live-fetch notebook.
- `outputs/gdelt_live_response.json`: saved live payload.

## Part 3 - Code Reference (Names and Structure)

- Notebook cell 1: capability and query preview.
- Notebook cell 2: live fetch, title/url printing, payload persistence.

How to run:
- Open and run notebook cells in `gdelt_api_explorer.ipynb`.
