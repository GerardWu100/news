/**
 * Browser application controller for search and pagination flows.
 *
 * This module wires DOM events to the API client, tracks request lifecycle
 * state, and delegates all UI updates to rendering helpers.
 */

import { fetchConfig, fetchSearch, fetchSources } from "./api.js";
import {
    applySearchFormFromUrl,
    buildApiParams,
    buildExportUrl,
    copyCurrentUrl,
    readSearchForm,
    setDefaultDates,
    syncQueryToUrl,
} from "./form.js";
import {
    announce,
    closeArticleDialog,
    clearStatus,
    renderEmptyState,
    renderError,
    renderArticleDialog,
    renderMeta,
    renderPagination,
    renderResearchWindow,
    renderResultActions,
    renderResults,
    renderSourceReports,
    renderSources,
    renderSpinner,
    setResultsBusy,
} from "./render.js";
import { setCurrentResults, setMeta, setPage, startSearch, state } from "./state.js";

const EMPTY_PAGE_STATE = {
    currentPage: 1,
    hasPrevious: false,
    hasMore: false,
    isLoading: false,
};

const searchFormElement = document.getElementById("search-form");
const searchButtonElement = document.getElementById("search-btn");
const queryInputElement = document.getElementById("query");
const nextPageButtonElement = document.getElementById("next-page-btn");
const previousPageButtonElement = document.getElementById("previous-page-btn");
const resultsElement = document.getElementById("results");
const articleDialogElement = document.getElementById("article-dialog");
const articleDialogCloseButtonElement = document.getElementById("article-dialog-close");
const copyLinkButtonElement = document.getElementById("copy-link-btn");

const SEARCH_BUTTON_IDLE_LABEL = searchButtonElement.textContent;

searchFormElement.addEventListener("submit", onSearchSubmit);
nextPageButtonElement.addEventListener("click", onNextPageClick);
previousPageButtonElement.addEventListener("click", onPreviousPageClick);
resultsElement.addEventListener("click", onResultClick);
articleDialogCloseButtonElement.addEventListener("click", onDialogCloseClick);
articleDialogElement.addEventListener("click", onDialogBackdropClick);
copyLinkButtonElement.addEventListener("click", onCopyLinkClick);
document.addEventListener("keydown", onGlobalKeydown);

void initializePage();


/**
 * Focus the query field when the user presses "/" outside a text field.
 *
 * Research tools commonly bind "/" to search. The handler ignores the key
 * while the user is already typing in a field or the article dialog is open so
 * it never swallows a literal slash.
 */
function onGlobalKeydown(event) {
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
        return;
    }
    if (articleDialogElement.open) {
        return;
    }
    const active = document.activeElement;
    const isTypingTarget = active
        && (active.tagName === "INPUT"
            || active.tagName === "TEXTAREA"
            || active.tagName === "SELECT"
            || active.isContentEditable);
    if (isTypingTarget) {
        return;
    }
    event.preventDefault();
    queryInputElement.focus();
    queryInputElement.select();
}


/**
 * Reflect the in-flight state on the primary search button.
 *
 * Disabling it during a request prevents overlapping submissions and gives a
 * clear "working" cue that the spinner alone does not, since the button sits
 * far above the results region.
 */
function setSearchButtonLoading(isLoading) {
    searchButtonElement.disabled = isLoading;
    searchButtonElement.textContent = isLoading ? "Searching..." : SEARCH_BUTTON_IDLE_LABEL;
}


function onNextPageClick() {
    void loadPage(state.currentPage + 1);
}


function onPreviousPageClick() {
    void loadPage(state.currentPage - 1);
}


function onDialogCloseClick() {
    closeArticleDialog();
}


function onDialogBackdropClick(event) {
    if (event.target.id === "article-dialog") {
        closeArticleDialog();
    }
}


function onCopyLinkClick() {
    void copyShareLink();
}


async function initializePage() {
    setDefaultDates();

    try {
        const [config, sources] = await Promise.all([fetchConfig(), fetchSources()]);
        const defaultSources = Array.isArray(config.default_sources)
            ? config.default_sources
            : ["guardian", "nyt"];
        if (config.default_english_only) {
            document.getElementById("english-only").checked = true;
        }
        renderSources(sources, defaultSources);

        const restoredPage = applySearchFormFromUrl();
        if (restoredPage !== null) {
            const restoredQuery = readSearchForm();
            if (restoredQuery && !restoredQuery.error) {
                startSearch(restoredQuery);
                renderSpinner();
                await executeSearch(restoredPage);
            }
        }
    } catch (error) {
        renderError(error.message);
    }
}


async function onSearchSubmit(event) {
    event.preventDefault();

    const query = readSearchForm();
    if (!query) {
        return;
    }
    if (query.error) {
        clearStatus();
        renderPagination(EMPTY_PAGE_STATE);
        renderError(query.error);
        return;
    }

    startSearch(query);
    closeArticleDialog();
    clearStatus();
    renderPagination(EMPTY_PAGE_STATE);
    renderSpinner();
    syncQueryToUrl(query, 1);
    scrollResultsIntoViewOnNarrowScreens();
    await executeSearch(1);
}


/**
 * On narrow screens the search form is tall enough to hide the results, so
 * bring the results region into view once a fresh search starts. Wide layouts
 * already show both columns and are left untouched.
 */
function scrollResultsIntoViewOnNarrowScreens() {
    if (window.matchMedia("(max-width: 820px)").matches) {
        resultsElement.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}


async function loadPage(page) {
    if (!state.activeQuery || state.isLoading) {
        return;
    }
    if (page < 1) {
        return;
    }
    closeArticleDialog();
    renderSpinner();
    await executeSearch(page);
}


async function executeSearch(requestedPage = state.currentPage) {
    if (!state.activeQuery) {
        return;
    }

    if (state.currentAbortController) {
        state.currentAbortController.abort();
    }
    const abortController = new AbortController();
    state.currentAbortController = abortController;

    state.isLoading = true;
    setSearchButtonLoading(true);
    setResultsBusy(true);
    announce(`Searching page ${requestedPage}...`);
    renderPagination({
        currentPage: requestedPage,
        hasPrevious: requestedPage > 1,
        hasMore: requestedPage === state.currentPage ? state.hasMore : false,
        isLoading: true,
    });

    try {
        const startedAt = performance.now();
        const payload = await fetchSearch(
            buildApiParams(state.activeQuery, requestedPage),
            abortController.signal,
        );
        const durationSeconds = ((performance.now() - startedAt) / 1000).toFixed(2);

        setPage(requestedPage);
        syncQueryToUrl(state.activeQuery, requestedPage);
        state.hasMore = payload.meta.has_more;
        state.hasPrevious = payload.meta.has_previous;
        setCurrentResults(payload.results);
        setMeta(payload.meta);

        if (payload.results.length === 0) {
            renderEmptyState("No results matched this provider page. Try broadening the date range, adding sources, or relaxing local filters.");
            announce("No results found for this provider page.");
        } else {
            renderResults(payload.results);
            const resultNoun = payload.results.length === 1 ? "result" : "results";
            announce(`${payload.results.length} ${resultNoun} on page ${requestedPage}.`);
        }

        renderMeta(payload.meta, durationSeconds);
        renderResearchWindow(payload.meta);
        renderResultActions(
            buildExportUrl("json", state.activeQuery, requestedPage),
            buildExportUrl("csv", state.activeQuery, requestedPage),
        );
        renderSourceReports(payload.meta.source_reports || []);
        renderPagination({
            currentPage: state.currentPage,
            hasPrevious: state.hasPrevious,
            hasMore: state.hasMore,
            isLoading: false,
        });
    } catch (error) {
        if (error.name === "AbortError") {
            return;
        }
        setCurrentResults([]);
        state.hasMore = false;
        state.hasPrevious = false;
        setMeta(null);
        clearStatus();
        renderError(error.message);
        announce(`Search failed: ${error.message}`);
        renderPagination({ ...EMPTY_PAGE_STATE, currentPage: state.currentPage });
    } finally {
        // Only the request that still owns the abort controller may release the
        // shared loading UI; a superseded request must leave it to its successor.
        if (state.currentAbortController === abortController) {
            state.isLoading = false;
            state.currentAbortController = null;
            setSearchButtonLoading(false);
            setResultsBusy(false);
        }
    }
}


function onResultClick(event) {
    const button = event.target.closest("[data-result-index]");
    if (!button) {
        return;
    }

    const index = Number(button.dataset.resultIndex);
    const result = state.currentResults[index];
    if (!result) {
        return;
    }

    renderArticleDialog(result);
}


async function copyShareLink() {
    const originalLabel = copyLinkButtonElement.textContent;

    try {
        await copyCurrentUrl();
        copyLinkButtonElement.textContent = "Link copied";
    } catch {
        copyLinkButtonElement.textContent = "Copy failed";
    }

    window.setTimeout(function resetCopyButtonLabel() {
        copyLinkButtonElement.textContent = originalLabel;
    }, 1600);
}
