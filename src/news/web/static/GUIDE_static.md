# GUIDE_static

## Part 1 -- Conceptual Explanation

### Purpose

The `static/` folder contains the entire browser client: one HTML shell, one
CSS file, and a small set of JavaScript modules. These files ship with the
package so the browser works from both a source checkout and an installed
wheel. The frontend is dependency-light and focuses on retrieval:

- explaining the historical cutoff before the form,
- restoring searches from the browser URL,
- keeping the inclusive publication window visible as a date cutoff,
- displaying the current source page,
- showing the status of each source request,
- downloading the exact visible page as JSON or CSV,
- copying a shareable query link,
- keeping page navigation correct during asynchronous loads,
- opening an in-app article detail dialog,
- and drawing search attention for the same query and window.

## Search attention

The third section asks `GET /api/trends/interest` for the same query and dates
already in the search form. It deliberately has no query or date fields of its
own: attention only means something beside the articles from the same window,
and a second set of inputs would let the two drift apart without the reader
noticing. Only the geography and the decision date are section-specific,
because neither has any meaning for an article search.

The chart is inline SVG built by `trends.js`, not a charting library. The
page's Content Security Policy allows scripts only from this server, so no
external library can load, and a line chart needs far less code than shipping
one.

Two details of the drawing exist for a reason. The vertical axis is fixed at 0
to 100 rather than scaled to the data, because Google's index is already
relative and a self-scaling axis would make two incomparable windows look
alike. And the drawing is measured in the section's own pixel width instead of
a fixed box stretched to fit, because stretching scales the horizontal and
vertical axes by different amounts and distorts every label.

The section states in words what the numbers mean. Google scales every value to
the peak of the whole window requested, so a reader who takes 100 for "very
high" rather than "the highest point of this window" misreads the chart, and
the early part of a long window carries a peak that had not happened yet. The
decision date asks the server to rescale to what was known on that date.

The visual hierarchy follows the research workflow. The editorial masthead
states the purpose and the information-set rule; the numbered search workspace
collects inputs; the numbered archive section presents evidence. Before the
first search, that archive section teaches a short cutoff-read-record routine
instead of appearing empty. The first returned article is featured and later
articles fill as many columns as the window allows, collapsing to one column on
smaller screens.

The masthead is kept short on purpose. The search form is the reason to open
the page, so a tall introduction that pushes the form below the fold costs a
scroll on every single use. The masthead states the purpose and the cutoff rule
in a band that leaves the whole form visible on a laptop screen.

No band has a fixed width. Every full-width section is `width: 100%` with side
padding from the `--page-gutter` variable, which scales with the window. A fixed
maximum width in pixels would leave large empty margins on a wide screen and on
any zoomed-out view, where the reported viewport grows but the column does not.

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
├── index.html            -- HTML shell for the search interface, results area, and attention chart.
├── styles.css            -- Shared editorial theme, layout, cards, chart, and dialog styles.
└── scripts/
    ├── api.js            -- API helpers for config, sources, search, and trends calls.
    ├── app.js            -- UI coordination, submission, page navigation, export, and share-link actions.
    ├── form.js           -- Form reading, URL hydration/sync, and export/share-link helpers.
    ├── render.js         -- Cutoff, result, action, status, dialog, and safe-link display.
    ├── session.js        -- Signed-in account name and the sign-out form token.
    ├── state.js          -- In-memory state for the active search.
    └── trends.js         -- Search-attention section: request, SVG chart, legend, and scale caption.
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
- Sizes every layout band with `--page-gutter` and percentages rather than a
  fixed pixel column, and lets the result grid choose its own column count with
  `repeat(auto-fit, minmax(min(100%, 24rem), 1fr))`. The inner `min()` keeps a
  single column on narrow screens, where a fixed track would overflow.

### `scripts/api.js`

- `fetchConfig()`: fetches `/api/config`.
- `fetchSources()`: fetches `/api/sources`.
- `fetchSearch(params)`: fetches `/api/search` with the active query params.
- `fetchTrends(params)`: fetches `/api/trends/interest` for the same query and
  window.
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

### `scripts/trends.js`

- `loadAttention()`: reads the query and window from the search form, requests
  the series, and draws it. Bound to the section's own button on import.
- `measureChartBox()`: reads the section's current width and picks a drawing
  height from it, so the SVG never needs stretching.
- `buildChart(...)`, `buildGridLine(...)`, `buildDateLabels(...)`,
  `buildLine(...)`: assemble the SVG. Date labels are spaced by the width
  available rather than by a fixed count, so they do not overlap on a phone.
- `buildLegend(...)`: one colour swatch per keyword. The colour is written to
  the element because the stylesheet cannot know the keyword order.
- `describeSeries(...)`: states the geography, the point spacing, and what the
  value 100 means for this particular request.

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
- 2026-08-11: Shortened the masthead so the search form is visible without
  scrolling, and replaced the fixed 1240-pixel column with fluid full-width
  bands so the page fills the window at any size or zoom level.
- 2026-08-11: Added the search-attention section, and rewrote `styles.css` so
  each selector is defined once. The file had grown from two stylesheets
  concatenated, where 29 selectors were declared twice and the later copy
  silently won, so the value a reader found was often not the value in use.
