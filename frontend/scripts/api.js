/**
 * API client helpers for frontend search workflows.
 *
 * All calls return parsed JSON and raise `Error` with a user-friendly
 * backend message when the response is not successful.
 */

const API_ROOT = "";

export async function fetchConfig() {
    return fetchJson("/api/config");
}

export async function fetchSources() {
    return fetchJson("/api/sources");
}

export async function fetchSearch(params, signal = null) {
    const queryString = new URLSearchParams(params).toString();
    return fetchJson(`/api/search?${queryString}`, signal);
}

async function fetchJson(path, signal = null) {
    const options = {};
    if (signal) {
        options.signal = signal;
    }

    const response = await fetch(API_ROOT + path, options);
    if (!response.ok) {
        throw new Error(await extractApiError(response));
    }
    return response.json();
}

async function extractApiError(response) {
    try {
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const payload = await response.json();
            return payload.detail || `HTTP ${response.status}`;
        }
        return `HTTP ${response.status} ${response.statusText}`;
    } catch {
        return `HTTP ${response.status}`;
    }
}
