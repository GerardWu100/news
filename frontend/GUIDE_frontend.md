# GUIDE_frontend

## Part 1 -- Conceptual Explanation

### Purpose

The `frontend/` folder contains the entire browser client: one HTML shell, one
CSS file, and a small set of JavaScript modules. The frontend is still
dependency-light, but it now focuses only on retrieval:

- restoring searches from the browser URL,
- rendering the current provider page,
- showing per-source execution status,
- copying a shareable query link,
- keeping pagination state coherent during async loads,
- and opening an in-app article detail dialog.

It no longer renders analytics cards or breakdown charts.

### Logic spine

1. On load, the page fetches `/api/config` and `/api/sources`.
2. Configured default sources are preselected, and the default date range is initialized in browser-local calendar time.
3. If the browser URL already contains a search query, the form is hydrated from that URL and the search is rerun automatically.
4. When the form is submitted, obvious bad date ranges are rejected locally.
5. The active search state is mirrored into the browser URL.
6. `/api/search` is called with the selected parameters.
7. The page renders:
   - a search summary line,
   - a copy-link button,
   - source execution chips,
   - result cards,
   - previous/next provider-page controls.
8. Pagination requests the next or previous provider page without committing the new page number until the request succeeds.
9. Clicking a result card opens an in-app dialog that shows provider-supplied context text already present in the API response.
10. The article dialog link is rendered only after URL validation and attribute escaping.

## Part 2 -- Folder Tree and File Map

```text
frontend/
├── GUIDE_frontend.md     -- This documentation file.
├── index.html            -- HTML shell for the search interface and results area.
├── styles.css            -- Shared editorial theme, layout, cards, and dialog styles.
└── scripts/
    ├── api.js            -- API helpers for config, sources, and search calls.
    ├── app.js            -- UI orchestration, submission, pagination, and share-link actions.
    ├── form.js           -- Form reading, URL hydration, URL sync, and copy-link helpers.
    ├── render.js         -- Result, source-report, meta-bar, dialog, and link-sanitization rendering.
    └── state.js          -- In-memory state container for the active search.
```

## Part 3 -- Code Reference

### `index.html`

- Defines the hero, search form, advanced controls, results shell, pagination controls, and article dialog.
- Places the copy-link button beside the rendered meta summary instead of in a separate analytics section.
- Loads `/static/styles.css` and `/static/scripts/app.js`.

### `styles.css`

- Defines the warm editorial visual language, responsive form layout, result cards, and dialog styling.
- Keeps the results header simple: summary text plus the share-link button.

### `scripts/api.js`

- `fetchConfig()`: fetches `/api/config`.
- `fetchSources()`: fetches `/api/sources`.
- `fetchSearch(params)`: fetches `/api/search` with the active query params.

### `scripts/form.js`

- `setDefaultDates()`: fills the date inputs with a rolling local-time window.
- `applySearchFormFromUrl()`: restores form state from `window.location.search`.
- `readSearchForm()`: returns the current form values.
- `buildApiParams(...)`: converts form state into backend query params.
- `syncQueryToUrl(...)`: mirrors the active query back into the browser URL.
- `copyCurrentUrl()`: copies the current search URL to the clipboard.

### `scripts/render.js`

- `renderSources(...)`: draws source checkboxes and applies configured defaults.
- `renderMeta(...)`: shows the current provider page, counts, and latency.
- `renderSourceReports(...)`: shows source execution chips.
- `renderResults(...)`: renders the current page of result cards.
- `renderArticleDialog(...)`: opens the in-app detail dialog for one result.
- `buildSafeArticleUrl(...)`: validates dialog URLs before they are rendered.
- `escapeAttribute(...)`: escapes attribute values used in rendered links.
- `renderPagination(...)`: controls the previous/next page buttons and label.
- `clearStatus()`: clears the meta text and hides the copy-link button.

### `scripts/state.js`

- Stores the active query object, current results, current page, pagination flags, abort controller, and last metadata payload.

### `scripts/app.js`

- `initializePage()`
  - Loads config and source availability.
  - Applies configured defaults.
  - Restores and reruns URL-backed searches.
- `onSearchSubmit(...)`
  - Reads and validates the form.
  - Starts a new search state and syncs the URL.
- `executeSearch(...)`
  - Calls the backend.
  - Updates pagination state only after success.
  - Shows the copy-link button only after a successful search.
- `copyShareLink()`
  - Copies the current search URL and briefly acknowledges success or failure.
