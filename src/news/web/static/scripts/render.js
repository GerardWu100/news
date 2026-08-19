/**
 * Helpers that update parts of the browser search page.
 *
 * Each function owns one page area, so the controller can focus on requests
 * and search state.
 */

const RESULTS_CONTAINER_ID = "results";
const META_BAR_ID = "meta-bar";
const STATUS_STRIP_ID = "status-strip";
const RESULT_ACTIONS_ID = "result-actions";
const WINDOW_BANNER_ID = "window-banner";
const A11Y_STATUS_ID = "a11y-status";
const SEARCH_BUTTON_ID = "search-btn";

// Each result card starts its entrance animation slightly after the one above
// it, up to a cap so a full page of results does not crawl in.
const CARD_ENTRANCE_STEP_SECONDS = 0.03;
const MAX_CARD_ENTRANCE_DELAY_SECONDS = 0.3;

/**
 * Announce a short status message to screen readers.
 *
 * Replacing the results area does not reliably produce an announcement. This
 * writes a short sentence to a dedicated live region instead.
 *
 * Functions that replace the results area announce their own outcome, so each
 * visible state also has an audible description.
 *
 * Parameters
 * ----------
 * message : string
 *     Status such as "12 results found" or "Search failed".
 */
function announce(message) {
    document.getElementById(A11Y_STATUS_ID).textContent = message;
}

/**
 * Show that a request is running on the search button and results area.
 *
 * Disabling the button prevents overlapping submissions and makes the state
 * clear even though the button is far above the results. ``aria-busy`` tells
 * assistive technology that the region is being updated.
 *
 * Parameters
 * ----------
 * isLoading : boolean
 *     Whether a search request is currently in flight.
 */
export function setSearchLoading(isLoading) {
    const searchButton = document.getElementById(SEARCH_BUTTON_ID);
    searchButton.disabled = isLoading;
    searchButton.textContent = isLoading ? "Searching..." : "Search";
    document.getElementById(RESULTS_CONTAINER_ID)
        .setAttribute("aria-busy", String(isLoading));
}

/**
 * Make one value safe to place anywhere in an HTML template.
 *
 * Article text arrives from outside sources, so it is never trusted. Angle
 * brackets and ampersands are escaped so the value cannot start a tag, and
 * both quote characters are escaped so it cannot end an attribute either. One
 * escaper that is safe in both places means a caller can never pick the wrong
 * one.
 *
 * Parameters
 * ----------
 * value : string
 *     Untrusted text, or any value that converts to text.
 *
 * Returns
 * -------
 * string
 *     Text safe for element content and for a quoted attribute value.
 */
function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}


function buildSafeArticleUrl(rawUrl) {
    if (!rawUrl) {
        return "";
    }

    try {
        const parsedUrl = new URL(rawUrl, window.location.origin);
        if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
            return "";
        }
        return parsedUrl.toString();
    } catch (_error) {
        return "";
    }
}


export function renderSources(sources, defaultSources = []) {
    const container = document.getElementById("source-checks");
    const useAllAvailableDefaults = defaultSources.length === 0;
    container.innerHTML = sources.map(function buildSourceCheckbox(source) {
        const disabled = source.available ? "" : "disabled";
        const shouldCheck = source.available
            && (useAllAvailableDefaults || defaultSources.includes(source.name));
        const checked = shouldCheck ? "checked" : "";
        const label = source.available
            ? source.display_name
            : `${source.display_name} (no key)`;
        return `
            <label class="checkbox-label source-pill">
                <input type="checkbox" name="source" value="${escapeHtml(source.name)}" ${checked} ${disabled}>
                <span>${escapeHtml(label)}</span>
            </label>
        `;
    }).join("");
}


export function renderMeta(meta, queryDurationSeconds) {
    const metaBar = document.getElementById(META_BAR_ID);
    metaBar.innerHTML = `
        <span class="meta-primary">Source page ${meta.page} for "<strong>${escapeHtml(meta.query)}</strong>"</span>
        <span class="meta-secondary">${meta.returned} results, ${meta.total_before_deduplication} before duplicate removal, ${meta.duplicates_removed} duplicates removed, ${queryDurationSeconds}s</span>
    `;
}

/**
 * Show the date cutoff used for the completed search.
 *
 * The banner keeps the date cutoff visible beside the results, where it is
 * harder to forget during historical research.
 */
export function renderResearchWindow(meta) {
    const banner = document.getElementById(WINDOW_BANNER_ID);
    banner.innerHTML = `
        <span>Date cutoff</span>
        <strong>${escapeHtml(meta.start)} through ${escapeHtml(meta.end)}</strong>
        <small>Inclusive source publication dates; later coverage is outside this view.</small>
    `;
    banner.hidden = false;
}

/**
 * Point the download controls at the visible page and show them.
 */
export function renderResultActions(jsonUrl, csvUrl) {
    document.getElementById("json-export-link").href = jsonUrl;
    document.getElementById("csv-export-link").href = csvUrl;
    document.getElementById(RESULT_ACTIONS_ID).hidden = false;
}


export function renderSourceReports(reports) {
    const container = document.getElementById(STATUS_STRIP_ID);
    container.innerHTML = reports.map(function renderReport(report) {
        const statusClass = getReportStatusClass(report);
        const message = getReportMessage(report);
        return `<span class="${statusClass}"><strong>${escapeHtml(report.display_name)}</strong> ${message}</span>`;
    }).join("");
}


export function renderResults(results, page) {
    const container = document.getElementById(RESULTS_CONTAINER_ID);
    const html = results.map(function renderResultCard(result, index) {
        return createResultCard(result, index);
    }).join("");
    container.innerHTML = html;
    applyCardEntranceDelays(container);
    const resultNoun = results.length === 1 ? "result" : "results";
    announce(`${results.length} ${resultNoun} on page ${page}.`);
}

/**
 * Stagger the entrance animation of the freshly inserted result cards.
 *
 * The delay is set through the style property rather than a ``style``
 * attribute in the card markup. The page's Content Security Policy does not
 * allow inline style attributes, but it does allow a script to write to an
 * element's style, so the animation survives the stricter policy.
 *
 * Parameters
 * ----------
 * container : Element
 *     Results container whose cards were just replaced.
 */
function applyCardEntranceDelays(container) {
    const cards = container.querySelectorAll(".result-card");
    cards.forEach(function setEntranceDelay(card, index) {
        const delaySeconds = Math.min(index * CARD_ENTRANCE_STEP_SECONDS,
            MAX_CARD_ENTRANCE_DELAY_SECONDS);
        card.style.animationDelay = `${delaySeconds}s`;
    });
}


export function renderEmptyState(message) {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML =
        `<div class="empty-state">${escapeHtml(message)}</div>`;
    announce(message);
}


export function renderSpinner() {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML = `
        <div class="spinner">
            <div class="spinner-icon"></div>
            <div>Searching the news archives...</div>
        </div>
    `;
    announce("Searching the news archives...");
}


export function renderError(message) {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML =
        `<div class="error-msg">Search failed: ${escapeHtml(message)}</div>`;
    announce(`Search failed: ${message}`);
}


export function clearStatus() {
    document.getElementById(META_BAR_ID).innerHTML = "";
    document.getElementById(STATUS_STRIP_ID).innerHTML = "";
    document.getElementById(RESULT_ACTIONS_ID).hidden = true;
    document.getElementById(WINDOW_BANNER_ID).hidden = true;
}


export function renderPagination({
    currentPage,
    hasPrevious,
    hasMore,
    isLoading,
}) {
    const shell = document.getElementById("pagination-shell");
    const previousButton = document.getElementById("previous-page-btn");
    const nextButton = document.getElementById("next-page-btn");
    const label = document.getElementById("pagination-label");

    const showPager = hasPrevious || hasMore;
    shell.hidden = !showPager;
    previousButton.disabled = isLoading || !hasPrevious;
    nextButton.disabled = isLoading || !hasMore;
    label.textContent = `Page ${currentPage}`;
    nextButton.textContent = isLoading ? "Loading..." : "Next page";
}


export function renderArticleDialog(result) {
    const dialog = document.getElementById("article-dialog");
    const body = document.getElementById("article-dialog-body");
    body.innerHTML = createArticleDialogContent(result);
    dialog.showModal();
}


export function closeArticleDialog() {
    const dialog = document.getElementById("article-dialog");
    if (dialog.open) {
        dialog.close();
    }
}


function createResultCard(result, index) {
    const preview = truncateText(result.summary || result.content || "", 280);
    return `
        <article class="result-card source-${escapeHtml(result.source)}">
            <div class="result-card-topline">
                <div class="result-card-badges">${renderSourceBadges(result)}</div>
                ${result.date ? `<span class="result-card-date">${escapeHtml(result.date)}</span>` : ""}
            </div>
            <button class="result-open-btn" type="button" data-result-index="${index}">
                ${escapeHtml(result.title || "Untitled")}
            </button>
            ${preview ? `<p class="result-preview">${escapeHtml(preview)}</p>` : ""}
            <div class="result-meta">
                ${result.domain ? `<span>Domain ${escapeHtml(result.domain)}</span>` : ""}
                ${result.language ? `<span>Language ${escapeHtml(result.language.toUpperCase())}</span>` : ""}
                ${result.section ? `<span>Section ${escapeHtml(result.section)}</span>` : ""}
                ${result.duplicate_count > 1 ? `<span class="duplicate-pill">${escapeHtml(String(result.duplicate_count))} merged records</span>` : ""}
            </div>
        </article>
    `;
}


function renderSourceBadges(result) {
    const sources = (result.matched_sources && result.matched_sources.length)
        ? result.matched_sources
        : [result.source];

    return sources.map(function buildSourceBadge(source) {
        const safeSource = escapeHtml(source);
        return `<span class="badge badge-${safeSource}">${safeSource}</span>`;
    }).join("");
}


function createArticleDialogContent(result) {
    const bodyText = result.content || result.summary || "No source text is available for this article.";
    const safeUrl = buildSafeArticleUrl(result.url);
    return `
        <div class="article-dialog-header">
            <div class="article-dialog-badges">${renderSourceBadges(result)}</div>
            <h2>${escapeHtml(result.title || "Untitled")}</h2>
            <div class="article-dialog-meta">
                ${result.date ? `<span>${escapeHtml(result.date)}</span>` : ""}
                ${result.domain ? `<span>${escapeHtml(result.domain)}</span>` : ""}
                ${result.section ? `<span>${escapeHtml(result.section)}</span>` : ""}
                ${result.author ? `<span>${escapeHtml(result.author)}</span>` : ""}
            </div>
        </div>
        ${result.summary ? `<p class="article-dialog-summary">${escapeHtml(result.summary)}</p>` : ""}
        <div class="article-dialog-text">${escapeHtml(bodyText)}</div>
        ${safeUrl ? `<a class="article-dialog-link" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener">Open source article</a>` : ""}
    `;
}


function truncateText(value, maxLength) {
    if (!value || value.length <= maxLength) {
        return value;
    }
    return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}


function getReportStatusClass(report) {
    if (report.error) {
        return "status-chip status-chip-error";
    }
    if (report.available) {
        return "status-chip";
    }
    return "status-chip status-chip-muted";
}


function getReportMessage(report) {
    if (report.error) {
        return escapeHtml(report.error);
    }
    if (!report.available) {
        return "Unavailable";
    }
    if (report.has_more) {
        return `${report.returned} found, more available`;
    }
    return `${report.returned} found`;
}
