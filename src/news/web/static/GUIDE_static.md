# GUIDE_static

## Part 1 -- Conceptual Explanation

### Purpose

The `static/` folder contains the entire browser client: one HTML shell, one
CSS file, and a small set of JavaScript modules. These files ship with the
package so the browser works from both a source checkout and an installed
wheel. The frontend is dependency-light and focuses only on retrieval:

- explaining the historical cutoff before the form,
- restoring searches from the browser URL,
- keeping the inclusive publication window visible as a date cutoff,
- displaying the current source page,
- showing the status of each source request,
- downloading the exact visible page as JSON or CSV,
- copying a shareable query link,
- keeping page navigation correct during asynchronous loads,
- and opening an in-app article detail dialog.

It no longer shows analytics cards or breakdown charts.

The visual hierarchy follows the research workflow. The editorial masthead
states the purpose and the information-set rule; the numbered search workspace
collects inputs; the numbered archive section presents evidence. Before the
first search, that archive section teaches a short cutoff-read-record routine
instead of appearing empty. On wider screens, the first returned article is
featured and later articles use a two-column grid; the layout collapses to one
column on smaller screens.

The hero feature badges use explicit list and list-item semantics so assistive
technology receives the same grouping visible in the layout.

The page is served only to a signed-in browser. Two things follow from that.
The page asks the server who is signed in and fills the sign-out button's token
from the answer, because a static file cannot carry a server-issued token. And
any API call that comes back as 401, which is what an expired session looks
like, sends the reader to the sign-in page instead of showing a search error.

### Logic spine

0. The page loads the current session, shows the account name in the masthead,
   and fills the sign-out form's token.
1. On load, the page fetches `/api/config` and `/api/sources`.
2. Configured default sources are preselected, and the default date range is initialized in browser-local calendar time.
3. If the browser URL already contains a search query, the form is restored from that URL and the search runs again automatically.
4. When the form is submitted, obvious bad date ranges are rejected locally.
5. The active search state is mirrored into the browser URL.
6. `/api/search` is called with the selected parameters.
7. The page displays:
   - the active historical date window,
   - a search summary line,
   - JSON, CSV, and copy-link actions,
   - source execution chips,
   - result cards,
   - previous/next provider-page controls.
8. Page navigation requests the next or previous source page without changing the page number until the request succeeds.
9. Clicking a result card opens an in-app dialog that shows provider-supplied context text already present in the API response.
10. The article dialog link appears only after URL validation and attribute escaping.

## Part 2 -- Folder Tree and File Map

```text
static/
├── favicon.svg           -- Packaged browser-tab mark matching the masthead.
├── GUIDE_static.md       -- This documentation file.
├── index.html            -- HTML shell for the search interface and results area.
├── styles.css            -- Shared editorial theme, layout, cards, and dialog styles.
└── scripts/
    ├── api.js            -- API helpers for config, sources, and search calls.
    ├── app.js            -- UI coordination, submission, page navigation, export, and share-link actions.
    ├── form.js           -- Form reading, URL hydration/sync, and export/share-link helpers.
    ├── render.js         -- Cutoff, result, action, status, dialog, and safe-link display.
    ├── session.js        -- Signed-in account name and the sign-out form token.
    └── state.js          -- In-memory state for the active search.
```

## Part 3 -- Code Reference

### `index.html`

- Defines the purpose statement, labelled historical-window form, advanced
  controls, research-method card, first-use instructions, information-boundary
  banner, result actions, pagination, and dialog.
- Places exact-page JSON/CSV downloads and the copy-link button beside the
  displayed search summary.
- Holds the masthead account label and the sign-out form, whose token is filled
  in by script rather than written into the file.
- Loads the packaged SVG favicon, stylesheet, and both JavaScript entrypoints.

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
- A 401 from any of these sends the browser to `/login`, because an expired
  session makes every call fail the same way.

### `scripts/session.js`

- `loadSession()`: reads `/api/session`, writes the account name into the
  masthead label, and fills the hidden sign-out token. Runs on import.

### `scripts/form.js`

- `setDefaultDates()`: fills the date inputs with a rolling local-time window.
- `applySearchFormFromUrl()`: restores form state from `window.location.search`.
- `readSearchForm()`: returns the current form values.
- `buildApiParams(...)`: converts form state into backend query params.
- `buildExportUrl(...)`: builds an exact-page JSON or CSV URL from active state.
- `syncQueryToUrl(...)`: mirrors the active query back into the browser URL.
- `copyCurrentUrl()`: copies the current search URL to the clipboard.
- `focusQueryField()`: focuses and selects the topic input, so field ids stay
  declared only in this module.

### `scripts/render.js`

Every function that replaces the results region also writes a short sentence to
the polite live region, so a caller cannot display a state that a screen reader
never hears.

- `setSearchLoading(...)`: disables and relabels the search button and sets
  `aria-busy` on the results region for the duration of a request.
- `renderSources(...)`: draws source checkboxes and applies configured defaults.
- `renderMeta(...)`: shows the current source page and counts.
- `renderResearchWindow(...)`: shows the inclusive date cutoff.
- `renderResultActions(...)`: binds exact-page JSON and CSV downloads.
- `renderSourceReports(...)`: shows source request status chips.
- `renderResults(...)`: displays the current page of result cards and announces
  how many landed on which page.
- `applyCardEntranceDelays(...)`: staggers the card entrance animation through
  the style property. The page's Content Security Policy forbids inline style
  attributes, but allows a script to write to an element's style.
- `renderArticleDialog(...)`: opens the in-app detail dialog for one result.
- `buildSafeArticleUrl(...)`: validates dialog URLs before they are displayed.
- `escapeHtml(...)`: the single escaper. It escapes angle brackets, ampersands,
  and both quote characters, so one function is safe in element content and in
  a quoted attribute and a caller cannot pick the wrong one.
- `renderPagination(...)`: controls the previous/next page buttons and label.
- `clearStatus()`: clears result status and hides the boundary and action group.

### `scripts/state.js`

    - Stores the active query object, current results, current page, page flags, request-cancellation controller, and last search details.

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
- 2026-08-10: Kept the sign-in page server-rendered instead of adding it here,
  because a static file cannot carry the one-time token the form must return.
