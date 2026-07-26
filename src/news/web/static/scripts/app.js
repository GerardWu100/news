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
} from "./render.js";
import { setCurrentResults, setMeta, setPage, startSearch, state } from "./state.js";

const EMPTY_PAGE_STATE = {
    currentPage: 1,
    hasPrevious: false,
    hasMore: false,
    isLoading: false,
};

const searchFormElement = document.getElementById("search-form");
const nextPageButtonElement = document.getElementById("next-page-btn");
const previousPageButtonElement = document.getElementById("previous-page-btn");
const resultsElement = document.getElementById("results");
const articleDialogElement = document.getElementById("article-dialog");
const articleDialogCloseButtonElement = document.getElementById("article-dialog-close");
const copyLinkButtonElement = document.getElementById("copy-link-btn");

searchFormElement.addEventListener("submit", onSearchSubmit);
nextPageButtonElement.addEventListener("click", onNextPageClick);
previousPageButtonElement.addEventListener("click", onPreviousPageClick);
resultsElement.addEventListener("click", onResultClick);
articleDialogCloseButtonElement.addEventListener("click", onDialogCloseClick);
articleDialogElement.addEventListener("click", onDialogBackdropClick);
copyLinkButtonElement.addEventListener("click", onCopyLinkClick);

void initializePage();


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
    await executeSearch(1);
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
        } else {
            renderResults(payload.results);
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
        renderPagination({ ...EMPTY_PAGE_STATE, currentPage: state.currentPage });
    } finally {
        if (state.currentAbortController === abortController) {
            state.isLoading = false;
            state.currentAbortController = null;
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
