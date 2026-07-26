/**
 * Rendering helpers for the browser search interface.
 *
 * Each function updates one UI region so controller logic can stay focused on
 * request orchestration and state transitions.
 */

const RESULTS_CONTAINER_ID = "results";
const META_BAR_ID = "meta-bar";
const STATUS_STRIP_ID = "status-strip";
const RESULT_ACTIONS_ID = "result-actions";
const WINDOW_BANNER_ID = "window-banner";

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML;
}


function escapeAttribute(value) {
    return escapeHtml(value)
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
    container.innerHTML = sources.map(function buildSourceCheckbox(source) {
        const disabled = source.available ? "" : "disabled";
        const shouldCheck = source.available && defaultSources.includes(source.name);
        const checked = shouldCheck ? "checked" : "";
        const label = source.available
            ? source.display_name
            : `${source.display_name} (no key)`;
        return `
            <label class="checkbox-label source-pill">
                <input type="checkbox" name="source" value="${source.name}" ${checked} ${disabled}>
                <span>${escapeHtml(label)}</span>
            </label>
        `;
    }).join("");
}


export function renderMeta(meta, queryDurationSeconds) {
    const metaBar = document.getElementById(META_BAR_ID);
    metaBar.innerHTML = `
        <span class="meta-primary">Provider page ${meta.page} for "<strong>${escapeHtml(meta.query)}</strong>"</span>
        <span class="meta-secondary">${meta.returned} visible results, ${meta.total_before_deduplication} raw rows, ${meta.duplicates_removed} duplicates removed, ${queryDurationSeconds}s</span>
    `;
}

/**
 * Show the point-in-time boundary used for the completed search.
 *
 * The banner makes the temporal research contract visible beside the results,
 * where it is harder to forget during discretionary market practice.
 */
export function renderResearchWindow(meta) {
    const banner = document.getElementById(WINDOW_BANNER_ID);
    banner.innerHTML = `
        <span>Information set</span>
        <strong>${escapeHtml(meta.start)} through ${escapeHtml(meta.end)}</strong>
        <small>Inclusive provider publication dates; later coverage is outside this view.</small>
    `;
    banner.hidden = false;
}

/**
 * Point export controls at the exact active page and reveal the action group.
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


export function renderResults(results) {
    const container = document.getElementById(RESULTS_CONTAINER_ID);
    const html = results.map(function renderResultCard(result, index) {
        return createResultCard(result, index);
    }).join("");
    container.innerHTML = html;
}


export function renderEmptyState(message) {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML =
        `<div class="empty-state">${escapeHtml(message)}</div>`;
}


export function renderSpinner() {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML = `
        <div class="spinner">
            <div class="spinner-icon"></div>
            <div>Searching the archives...</div>
        </div>
    `;
}


export function renderError(message) {
    document.getElementById(RESULTS_CONTAINER_ID).innerHTML =
        `<div class="error-msg">Search failed: ${escapeHtml(message)}</div>`;
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
    nextButton.textContent = isLoading ? "Loading..." : "Next Page";
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
        <article class="result-card source-${result.source}" style="animation-delay: ${Math.min(index * 0.03, 0.3)}s">
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
                ${result.duplicate_count > 1 ? `<span class="duplicate-pill">${result.duplicate_count} merged records</span>` : ""}
            </div>
        </article>
    `;
}


function renderSourceBadges(result) {
    const sources = (result.matched_sources && result.matched_sources.length)
        ? result.matched_sources
        : [result.source];

    return sources.map(function buildSourceBadge(source) {
        return `<span class="badge badge-${source}">${escapeHtml(source)}</span>`;
    }).join("");
}


function createArticleDialogContent(result) {
    const bodyText = result.content || result.summary || "No provider text available for this record.";
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
        ${safeUrl ? `<a class="article-dialog-link" href="${escapeAttribute(safeUrl)}" target="_blank" rel="noopener">Open original article</a>` : ""}
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
        return `${report.returned} fetched, more available`;
    }
    return `${report.returned} fetched`;
}
