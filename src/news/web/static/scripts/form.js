/**
 * Form and URL helpers for the browser search experience.
 *
 * The module keeps query parsing and serialization in one place so UI code can
 * treat searches as plain objects.
 */

const DEFAULT_LOOKBACK_DAYS = 30;
const DEFAULT_PAGE_NUMBER = 1;

const QUERY_INPUT_ID = "query";
const START_DATE_INPUT_ID = "start-date";
const END_DATE_INPUT_ID = "end-date";
const ENGLISH_ONLY_INPUT_ID = "english-only";
const DEDUPE_INPUT_ID = "dedupe";

const ADVANCED_FIELD_ID_BY_PARAM = {
    exact_phrase: "exact-phrase",
    exclude_terms: "exclude-terms",
    domain: "domain-filter",
    exclude_domains: "exclude-domains",
    search_scope: "search-scope",
    match_mode: "match-mode",
    provider_sort: "provider-sort",
    section: "section-filter",
    news_desk: "news-desk-filter",
    guardian_tag: "guardian-tag-filter",
    newsapi_search_in: "newsapi-search-in",
    sort: "sort-order",
};


/**
 * Move keyboard focus to the topic field and select whatever it holds.
 *
 * Kept here so form-field ids stay declared in one module.
 */
export function focusQueryField() {
    const queryInput = getElement(QUERY_INPUT_ID);
    queryInput.focus();
    queryInput.select();
}


export function setDefaultDates() {
    const startDateInput = getElement(START_DATE_INPUT_ID);
    const endDateInput = getElement(END_DATE_INPUT_ID);
    if (startDateInput.value && endDateInput.value) {
        return;
    }

    const now = new Date();
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - DEFAULT_LOOKBACK_DAYS);
    startDateInput.value = formatLocalDate(startDate);
    endDateInput.value = formatLocalDate(now);
}


export function applySearchFormFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("q")?.trim();
    const startDate = params.get("start")?.trim();
    const endDate = params.get("end")?.trim();

    if (!query || !startDate || !endDate) {
        return null;
    }

    getElement(QUERY_INPUT_ID).value = query;
    getElement(START_DATE_INPUT_ID).value = startDate;
    getElement(END_DATE_INPUT_ID).value = endDate;

    if (params.has("sources")) {
        const selectedSources = new Set(
            (params.get("sources") || "")
                .split(",")
                .map(function trimSourceValue(value) {
                    return value.trim();
                })
                .filter(Boolean),
        );
        document.querySelectorAll('input[name="source"]').forEach(function applySourceSelection(checkbox) {
            checkbox.checked = selectedSources.has(checkbox.value);
        });
    }

    if (params.has("language")) {
        getElement(ENGLISH_ONLY_INPUT_ID).checked = (params.get("language") || "")
            .toLowerCase() === "en";
    }
    if (params.has("dedupe")) {
        getElement(DEDUPE_INPUT_ID).checked = parseBoolean(
            params.get("dedupe"),
            true,
        );
    }

    for (const [paramName, fieldId] of Object.entries(ADVANCED_FIELD_ID_BY_PARAM)) {
        setFieldValue(fieldId, params.get(paramName));
    }

    return parsePositiveInteger(params.get("page"), DEFAULT_PAGE_NUMBER);
}


export function readSearchForm() {
    const query = getElement(QUERY_INPUT_ID).value.trim();
    const startDate = getElement(START_DATE_INPUT_ID).value;
    const endDate = getElement(END_DATE_INPUT_ID).value;

    if (!query) {
        return null;
    }
    if (startDate && endDate && startDate > endDate) {
        return { error: "Start date must be on or before end date." };
    }

    const selectedSourceValues = [];
    const selectedSourceCheckboxes = document.querySelectorAll('input[name="source"]:checked');
    for (const checkbox of selectedSourceCheckboxes) {
        selectedSourceValues.push(checkbox.value);
    }

    return {
        query,
        startDate,
        endDate,
        selectedSources: selectedSourceValues,
        englishOnly: getElement(ENGLISH_ONLY_INPUT_ID).checked,
        dedupe: getElement(DEDUPE_INPUT_ID).checked,
        exactPhrase: getElement("exact-phrase").value.trim(),
        excludeTerms: getElement("exclude-terms").value.trim(),
        includeDomains: getElement("domain-filter").value.trim(),
        excludeDomains: getElement("exclude-domains").value.trim(),
        searchScope: getElement("search-scope").value,
        matchMode: getElement("match-mode").value,
        providerSort: getElement("provider-sort").value,
        section: getElement("section-filter").value.trim(),
        newsDesk: getElement("news-desk-filter").value.trim(),
        guardianTag: getElement("guardian-tag-filter").value.trim(),
        newsApiSearchIn: getElement("newsapi-search-in").value,
        sortOrder: getElement("sort-order").value,
    };
}


export function buildApiParams(query, page) {
    const params = {
        q: query.query,
        start: query.startDate,
        end: query.endDate,
        dedupe: String(query.dedupe),
        page: String(page),
        exact_phrase: query.exactPhrase,
        exclude_terms: query.excludeTerms,
        domain: query.includeDomains,
        exclude_domains: query.excludeDomains,
        search_scope: query.searchScope,
        match_mode: query.matchMode,
        provider_sort: query.providerSort,
        section: query.section,
        news_desk: query.newsDesk,
        guardian_tag: query.guardianTag,
        newsapi_search_in: query.newsApiSearchIn,
        sort: query.sortOrder,
    };

    if (query.selectedSources.length) {
        params.sources = query.selectedSources.join(",");
    }
    if (query.englishOnly) {
        params.language = "en";
    }

    return params;
}

/**
 * Build a same-origin download URL for the active provider page.
 *
 * Parameters
 * ----------
 * format : string
 *     Export representation. Valid values are ``json`` and ``csv``.
 * query : object
 *     Validated browser search state.
 * page : number
 *     Provider page currently visible in the browser.
 *
 * Returns
 * -------
 * string
 *     Relative API URL carrying the exact active search parameters.
 */
export function buildExportUrl(format, query, page) {
    const params = new URLSearchParams(buildApiParams(query, page));
    return `/api/export/${format}?${params.toString()}`;
}


export function syncQueryToUrl(query, page) {
    const params = new URLSearchParams(buildApiParams(query, page));
    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState({}, "", url);
}


export async function copyCurrentUrl() {
    const url = window.location.href;
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = url;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
}


function setFieldValue(id, value) {
    if (value === null) {
        return;
    }
    document.getElementById(id).value = value;
}


function getElement(id) {
    return document.getElementById(id);
}


function parseBoolean(value, defaultValue) {
    if (value === null) {
        return defaultValue;
    }
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1") {
        return true;
    }
    if (normalized === "false" || normalized === "0") {
        return false;
    }
    return defaultValue;
}


function parsePositiveInteger(value, defaultValue) {
    const parsed = Number.parseInt(value || "", 10);
    if (Number.isNaN(parsed) || parsed < 1) {
        return defaultValue;
    }
    return parsed;
}


function formatLocalDate(date) {
    const year = String(date.getFullYear());
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}
