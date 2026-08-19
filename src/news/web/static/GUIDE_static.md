# GUIDE_static

## Purpose

`static/` is the complete Historical Market News Search browser client: one
HTML shell, one stylesheet, and small JavaScript modules. The files are
packaged so the browser works from a checkout and from an installed wheel.

The opening copy states the product's two purposes: human market-forecast
practice and date-limited news retrieval for AI-agent strategy backtests.

The client lets a reader:

- search an inclusive historical date window;
- restore a search from the browser URL;
- see the current page and each provider's status;
- download the visible page as JSON or CSV;
- copy a shareable link;
- move between provider pages safely during asynchronous requests;
- open article details in a dialog; and
- draw Google Trends attention for the same query and window.

## Search attention

The third section calls `GET /api/trends/interest` with the query and dates in
the main search form. It has its own geography and decision-date controls, but
no second query or date range, so the two sections cannot drift apart.

`trends.js` draws an inline SVG instead of loading a chart library. The vertical
axis always runs from 0 to 100 because the provider already returns a relative
index. The chart measures its own width so resizing does not distort the axes
or labels. The page explains that 100 means the peak of this request, not a
fixed search volume. A decision date drops later values and rescales the series
to the information available then.

The page follows the research order: explain the cutoff, collect the search,
show the archive, then show search attention. The first result is featured;
the rest fill the available columns and collapse to one column on narrow
screens. Full-width bands use the `--page-gutter` variable rather than a fixed
pixel column, so they continue to work at different window sizes and zoom
levels.

The hero badges use list semantics for assistive technology. The page requires
sign-in. It loads the account and sign-out token from the server, and sends a
401 response to `/login` instead of displaying a failed search.

An empty configured default-source list means every currently available source
is visibly checked. This matches the API rule that an omitted source list means
all available sources. Only the stylesheet, icon, and script modules are public
under `/static`; the search and documentation HTML are served only by their
guarded routes.

## Logic spine

1. Load the session, account name, and sign-out token.
2. Fetch `/api/config` and `/api/sources`.
3. Select configured defaults and set browser-local default dates.
4. Restore and rerun a search found in the URL.
5. Validate submitted dates locally and mirror the active search into the URL.
6. Call `/api/search` with the selected parameters.
7. Show the date cutoff, summary, downloads, source statuses, result cards, and
   page controls.
8. Change page only after the next or previous request succeeds.
9. Open provider-supplied context in a dialog; display its link only after URL
   validation and HTML escaping.

## Folder tree

```text
static/
├── favicon.svg           -- packaged tab icon
├── GUIDE_static.md       -- this guide
├── docs.html             -- documentation page
├── index.html            -- search page shell
├── styles.css            -- shared layout and visual styles
└── scripts/
    ├── api.js            -- config, source, search, and Trends requests
    ├── app.js            -- page startup, searches, paging, exports, and links
    ├── form.js           -- form state, URL state, and export URLs
    ├── render.js         -- status, results, dialogs, and safe links
    ├── session.js        -- account label and sign-out token
    ├── state.js          -- active search state
    └── trends.js         -- attention request, SVG chart, and legend
```

## Code reference

### HTML

- `index.html` contains the labelled search form, advanced controls, research
  instructions, result actions, pagination, and article dialog.
- `docs.html` explains the purpose, interfaces, providers, coverage reports,
  CLI, HTTP routes, Trends caveats, and limits. `/docs` serves it behind
  sign-in. It has no script tag because its policy allows no scripts.

### CSS

`styles.css` defines the masthead, workflow sections, forms, source states,
result cards, boundary message, actions, dialog, focus styles, reduced motion,
responsive breakpoints, and one-column fallbacks. The result grid uses
`repeat(auto-fit, minmax(min(100%, 24rem), 1fr))` so a narrow screen cannot
overflow.

### JavaScript modules

- `api.js`: `fetchConfig`, `fetchSources`, `fetchSearch`, and `fetchTrends`.
  Any 401 redirects to `/login`.
- `session.js`: `loadSession` fills the masthead and sign-out token.
- `form.js`: `setDefaultDates`, URL hydration, form reading, API parameters,
  export links, URL syncing, copying, and query-field focus.
- `render.js`: loading state, sources, metadata, cutoff, downloads, source
  reports, cards, safe article URLs, HTML escaping, dialogs, pagination, and
  status clearing. Result updates also write to the screen-reader live region.
- `trends.js`: request and draw the attention series; measures the chart,
  builds grid lines, labels, the line, legend, and plain-language description.
- `state.js`: stores the active query, results, page, request cancellation
  controller, and last search details.
- `app.js`: initializes the page, handles form submission, runs searches,
  updates state after success, and copies share links.

## Short journal

- 2026-08-19: Made empty source defaults visibly select every available source and limited public static routes to non-HTML assets.
- 2026-08-12: Replaced the abstract outcome-focused name and hero copy with Historical Market News Search and its two explicit uses.
- 2026-07-26: Packaged browser assets so installed wheels can serve them without the repository root.
- 2026-07-26: Kept the dependency-free editorial theme and made the research sequence drive the layout.
- 2026-08-10: Kept sign-in server-rendered because the form needs a one-time server token.
- 2026-08-11: Made the masthead shorter and the page bands fluid so the form stays visible across window sizes.
- 2026-08-11: Added search attention and removed duplicate CSS definitions so each selector has one source of truth.
