/**
 * Shared state for the browser search page.
 *
 * It stays small and mutable because the frontend uses browser JavaScript
 * modules instead of a component framework.
 */

export const state = {
    activeQuery: null,
    currentResults: [],
    currentPage: 1,
    hasMore: false,
    hasPrevious: false,
    isLoading: false,
    currentAbortController: null,
    lastMeta: null,
};


export function startSearch(query) {
    state.activeQuery = query;
    state.currentResults = [];
    state.currentPage = 1;
    state.hasMore = false;
    state.hasPrevious = false;
    state.isLoading = false;
    state.currentAbortController = null;
    state.lastMeta = null;
}


export function setPage(page) {
    state.currentPage = page;
}


export function setCurrentResults(results) {
    state.currentResults = results;
}


export function setMeta(meta) {
    state.lastMeta = meta;
}
