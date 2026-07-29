# GUIDE_static

## Part 1 -- Conceptual Explanation

### Purpose

The `static/` folder contains the entire browser client: one HTML shell, one
CSS file, and a small set of JavaScript modules. These assets ship as package
data so the browser works from both a source checkout and an installed wheel.
The frontend is dependency-light and focuses only on retrieval:

- explaining the point-in-time research method before the form,
- restoring searches from the browser URL,
- keeping the inclusive publication window visible as an information boundary,
- rendering the current provider page,
- showing per-source execution status,
- downloading the exact visible page as JSON or CSV,
- copying a shareable query link,
- keeping pagination state coherent during async loads,
- and opening an in-app article detail dialog.

It no longer renders analytics cards or breakdown charts.

The visual hierarchy follows the research workflow. The editorial masthead
states the purpose and the information-set rule; the numbered search workspace
collects inputs; the numbered archive section presents evidence. Before the
first search, that archive section teaches a short cutoff-read-record routine
instead of appearing empty. On wider screens, the first returned article is
featured and later articles use a two-column grid; the layout collapses to one
column on smaller screens.

The hero feature badges use explicit list and list-item semantics so assistive
technology receives the same grouping visible in the layout.

### Logic spine

1. On load, the page fetches `/api/config` and `/api/sources`.
2. Configured default sources are preselected, and the default date range is initialized in browser-local calendar time.
3. If the browser URL already contains a search query, the form is hydrated from that URL and the search is rerun automatically.
4. When the form is submitted, obvious bad date ranges are rejected locally.
5. The active search state is mirrored into the browser URL.
6. `/api/search` is called with the selected parameters.
7. The page renders:
   - the active point-in-time information window,
   - a search summary line,
   - JSON, CSV, and copy-link actions,
   - source execution chips,
   - result cards,
   - previous/next provider-page controls.
8. Pagination requests the next or previous provider page without committing the new page number until the request succeeds.
9. Clicking a result card opens an in-app dialog that shows provider-supplied context text already present in the API response.
10. The article dialog link is rendered only after URL validation and attribute escaping.

## Part 2 -- Folder Tree and File Map

```text
static/
├── favicon.svg           -- Packaged browser-tab mark matching the masthead.
├── GUIDE_static.md       -- This documentation file.
├── index.html            -- HTML shell for the search interface and results area.
├── styles.css            -- Shared editorial theme, layout, cards, and dialog styles.
└── scripts/
    ├── api.js            -- API helpers for config, sources, and search calls.
    ├── app.js            -- UI orchestration, submission, pagination, export, and share-link actions.
    ├── form.js           -- Form reading, URL hydration/sync, and export/share-link helpers.
    ├── render.js         -- Boundary, result, action, status, dialog, and safe-link rendering.
    └── state.js          -- In-memory state container for the active search.
```

## Part 3 -- Code Reference

### `index.html`

- Defines the purpose statement, labelled historical-window form, advanced
  controls, research-method card, first-use instructions, information-boundary
  banner, result actions, pagination, and dialog.
- Places exact-page JSON/CSV downloads and the copy-link button beside the
  rendered meta summary.
- Loads the packaged SVG favicon, stylesheet, and JavaScript entrypoint.

### `styles.css`

- Defines the editorial masthead, numbered workflow hierarchy, responsive form,
  selected-source states, first-use instructions, featured result, card grid,
  information boundary, result actions, and dialog styling.
- Provides visible keyboard focus, reduced-motion behavior, two responsive
  breakpoints, and one-column fallbacks for forms, instructions, and results.

### `scripts/api.js`

- `fetchConfig()`: fetches `/api/config`.
- `fetchSources()`: fetches `/api/sources`.
- `fetchSearch(params)`: fetches `/api/search` with the active query params.

### `scripts/form.js`

- `setDefaultDates()`: fills the date inputs with a rolling local-time window.
- `applySearchFormFromUrl()`: restores form state from `window.location.search`.
- `readSearchForm()`: returns the current form values.
- `buildApiParams(...)`: converts form state into backend query params.
- `buildExportUrl(...)`: builds an exact-page JSON or CSV URL from active state.
- `syncQueryToUrl(...)`: mirrors the active query back into the browser URL.
- `copyCurrentUrl()`: copies the current search URL to the clipboard.

### `scripts/render.js`

- `renderSources(...)`: draws source checkboxes and applies configured defaults.
- `renderMeta(...)`: shows the current provider page, counts, and latency.
- `renderResearchWindow(...)`: shows the inclusive information boundary.
- `renderResultActions(...)`: binds exact-page JSON and CSV downloads.
- `renderSourceReports(...)`: shows source execution chips.
- `renderResults(...)`: renders the current page of result cards.
- `renderArticleDialog(...)`: opens the in-app detail dialog for one result.
- `buildSafeArticleUrl(...)`: validates dialog URLs before they are rendered.
- `escapeAttribute(...)`: escapes attribute values used in rendered links.
- `renderPagination(...)`: controls the previous/next page buttons and label.
- `clearStatus()`: clears result status and hides the boundary and action group.

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
  - Shows the boundary and JSON/CSV/copy actions only after a successful search.
- `copyShareLink()`
  - Copies the current search URL and briefly acknowledges success or failure.

## Part 4 -- Short Journal

- 2026-07-26: Moved the browser assets into the Python package so installed wheels can serve them without locating a repository root.
- 2026-07-26: Kept the dependency-free editorial theme while making the
  research sequence—not decoration—the basis of the page hierarchy.
