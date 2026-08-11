/**
 * Search-attention section: how much the public searched for the same
 * keywords over the same window as the article search.
 *
 * The chart is built as inline SVG rather than with a charting library. The
 * page's Content Security Policy allows scripts only from this server, so no
 * external library can load, and drawing a line chart needs far less code than
 * shipping one.
 *
 * Two facts about the data shape everything here. Google reports a relative
 * index from 0 to 100, never counts, so the axis is labelled as an index. And
 * Google scales every value to the peak of the whole requested window, which
 * tells the early days about a spike that had not happened yet; the decision
 * date control asks the server to rescale to what was known on that date.
 */

import { fetchTrends } from "./api.js";
import { readSearchForm } from "./form.js";

const CHART_ID = "trends-chart";
const LEGEND_ID = "trends-legend";
const STATUS_ID = "trends-status";
const BUTTON_ID = "trends-btn";
const GEOGRAPHY_INPUT_ID = "trends-geo";
const AS_OF_INPUT_ID = "trends-as-of";
const SUMMARY_ID = "trends-summary";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// The chart is drawn in the section's own pixel width rather than in a fixed
// coordinate system stretched to fit. Stretching a fixed box would scale the
// horizontal and vertical axes by different amounts and distort every label.
const CHART_HEIGHT_RATIO = 0.34;
const MINIMUM_CHART_HEIGHT = 220;
const MAXIMUM_CHART_HEIGHT = 400;
const FALLBACK_CHART_WIDTH = 900;

const PADDING_LEFT = 44;
const PADDING_RIGHT = 16;
const PADDING_TOP = 16;
const PADDING_BOTTOM = 34;

// Google's index always runs 0 to 100, so the vertical axis is fixed. A scale
// that grew with the data would make two different windows look comparable
// when they are not.
const INDEX_MINIMUM = 0;
const INDEX_MAXIMUM = 100;
const HORIZONTAL_GRID_VALUES = [0, 25, 50, 75, 100];

// Enough distinct colours for the five keywords the server accepts.
const SERIES_COLORS = ["#c15538", "#27589b", "#2e6b39", "#9a5317", "#6b4a9a"];

const MAXIMUM_DATE_LABELS = 6;

// A date reads as "2015-06-30", about 70 pixels wide at the axis font size.
// Labels are spaced at least this far apart so they never overlap on a narrow
// screen, which decides how many fit rather than a fixed count.
const MINIMUM_LABEL_SPACING = 92;

const chartElement = document.getElementById(CHART_ID);
const legendElement = document.getElementById(LEGEND_ID);
const statusElement = document.getElementById(STATUS_ID);
const summaryElement = document.getElementById(SUMMARY_ID);
const buttonElement = document.getElementById(BUTTON_ID);
const geographyInputElement = document.getElementById(GEOGRAPHY_INPUT_ID);
const asOfInputElement = document.getElementById(AS_OF_INPUT_ID);

let activeAbortController = null;

buttonElement.addEventListener("click", function onShowAttentionClick() {
    void loadAttention();
});


/**
 * Fetch and draw the series for the query and window already in the form.
 *
 * The section deliberately has no query or date fields of its own. Attention
 * is only meaningful next to the articles from the same window, and a second
 * set of inputs would let the two drift apart without the reader noticing.
 */
async function loadAttention() {
    const query = readSearchForm();
    if (!query) {
        return;
    }
    if (query.error) {
        showStatus(query.error, true);
        return;
    }

    if (activeAbortController) {
        activeAbortController.abort();
    }
    const abortController = new AbortController();
    activeAbortController = abortController;

    setLoading(true);
    showStatus("Asking Google for search attention...", false);

    try {
        const series = await fetchTrends(
            buildTrendsParams(query),
            abortController.signal,
        );
        drawSeries(series);
    } catch (error) {
        if (error.name === "AbortError") {
            return;
        }
        clearChart();
        showStatus(error.message, true);
    } finally {
        if (activeAbortController === abortController) {
            activeAbortController = null;
            setLoading(false);
        }
    }
}


function buildTrendsParams(query) {
    const params = {
        q: query.query,
        start: query.startDate,
        end: query.endDate,
    };
    const geography = geographyInputElement.value.trim();
    if (geography) {
        params.geo = geography;
    }
    const asOfDate = asOfInputElement.value;
    if (asOfDate) {
        params.as_of = asOfDate;
    }
    return params;
}


function setLoading(isLoading) {
    buttonElement.disabled = isLoading;
    buttonElement.textContent = isLoading ? "Loading..." : "Show attention";
    chartElement.setAttribute("aria-busy", String(isLoading));
}


function showStatus(message, isError) {
    statusElement.textContent = message;
    statusElement.classList.toggle("trends-status-error", Boolean(isError));
}


function clearChart() {
    chartElement.replaceChildren();
    legendElement.replaceChildren();
    summaryElement.textContent = "";
}


/**
 * Draw one line per keyword and describe what the numbers mean.
 *
 * Parameters
 * ----------
 * series : object
 *     Response from `GET /api/trends/interest`: `keywords`, `dates`, a
 *     `values` object holding one array of numbers per keyword, and
 *     `anchor_date`, the date the values are scaled to.
 */
function drawSeries(series) {
    const dates = series.dates || [];
    const keywords = series.keywords || [];

    if (dates.length === 0 || keywords.length === 0) {
        clearChart();
        showStatus(
            "Google returned no attention data for this query and window.",
            false,
        );
        return;
    }

    chartElement.replaceChildren(buildChart(dates, keywords, series.values || {}));
    legendElement.replaceChildren(...buildLegend(keywords));
    summaryElement.textContent = describeSeries(series);
    showStatus("", false);
}


/**
 * Describe the scaling in words, because the numbers alone are misleading.
 *
 * A reader who takes 100 for "very high" rather than "the peak of this
 * window" will compare two charts that share no scale at all.
 */
function describeSeries(series) {
    const geography = series.geo ? series.geo : "worldwide";
    const anchor = series.anchor_date;
    const scaling = anchor
        ? `100 is the highest value on or before ${anchor}`
        : "100 is the highest value in this window";
    return `Relative interest, ${geography}, ${series.granularity || "daily"} points. `
        + `${scaling}, not a number of searches.`;
}


/**
 * Measure the space available and pick a drawing box that fits it.
 *
 * Drawing in the section's own pixel width means the SVG needs no stretching,
 * so a date label is exactly as wide as the font makes it.
 */
function measureChartBox() {
    const width = chartElement.clientWidth || FALLBACK_CHART_WIDTH;
    const height = Math.min(
        Math.max(width * CHART_HEIGHT_RATIO, MINIMUM_CHART_HEIGHT),
        MAXIMUM_CHART_HEIGHT,
    );
    return { width, height };
}


function buildChart(dates, keywords, valuesByKeyword) {
    const box = measureChartBox();
    const svg = document.createElementNS(SVG_NAMESPACE, "svg");
    svg.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute(
        "aria-label",
        `Search interest for ${keywords.join(", ")} from ${dates[0]} to ${dates[dates.length - 1]}`,
    );

    for (const gridValue of HORIZONTAL_GRID_VALUES) {
        svg.append(...buildGridLine(gridValue, box));
    }
    for (const label of buildDateLabels(dates, box)) {
        svg.append(label);
    }
    keywords.forEach(function addSeriesLine(keyword, index) {
        const values = valuesByKeyword[keyword];
        if (Array.isArray(values) && values.length > 0) {
            svg.append(buildLine(values, dates.length, index, box));
        }
    });
    return svg;
}


function buildGridLine(indexValue, box) {
    const y = verticalPosition(indexValue, box);

    const line = document.createElementNS(SVG_NAMESPACE, "line");
    line.setAttribute("x1", String(PADDING_LEFT));
    line.setAttribute("x2", String(box.width - PADDING_RIGHT));
    line.setAttribute("y1", String(y));
    line.setAttribute("y2", String(y));
    line.setAttribute("class", "trends-grid-line");

    const label = document.createElementNS(SVG_NAMESPACE, "text");
    label.setAttribute("x", String(PADDING_LEFT - 8));
    label.setAttribute("y", String(y + 4));
    label.setAttribute("text-anchor", "end");
    label.setAttribute("class", "trends-axis-text");
    label.textContent = String(indexValue);

    return [line, label];
}


/**
 * Label a few evenly spaced dates rather than every point.
 *
 * A six-month daily window holds about 180 dates, and printing them all would
 * produce an unreadable smear along the bottom edge. How many fit is decided
 * by the width available, not by a fixed count, because six labels that are
 * comfortable on a laptop overlap into each other on a phone. The first and
 * last labels are anchored inward so neither runs off the edge.
 */
function buildDateLabels(dates, box) {
    const drawableWidth = box.width - PADDING_LEFT - PADDING_RIGHT;
    const labelCount = Math.min(
        MAXIMUM_DATE_LABELS,
        Math.max(2, Math.floor(drawableWidth / MINIMUM_LABEL_SPACING)),
    );
    const step = Math.max(1, Math.ceil(dates.length / labelCount));
    const lastIndex = dates.length - 1;
    const labels = [];

    for (let index = 0; index < dates.length; index += step) {
        // The final step often lands short of the end, leaving a wide gap; use
        // the last date there so the axis states where the window closes.
        const isLastLabel = index + step > lastIndex;
        const dateIndex = isLastLabel ? lastIndex : index;

        const label = document.createElementNS(SVG_NAMESPACE, "text");
        label.setAttribute("x", String(horizontalPosition(dateIndex, dates.length, box)));
        label.setAttribute("y", String(box.height - 10));
        label.setAttribute("class", "trends-axis-text");
        if (index === 0) {
            label.setAttribute("text-anchor", "start");
        } else if (isLastLabel) {
            label.setAttribute("text-anchor", "end");
        } else {
            label.setAttribute("text-anchor", "middle");
        }
        label.textContent = dates[dateIndex];
        labels.push(label);
    }
    return labels;
}


function buildLine(values, pointCount, colorIndex, box) {
    const points = values.map(function toChartPoint(value, index) {
        return `${horizontalPosition(index, pointCount, box)},${verticalPosition(value, box)}`;
    });

    const path = document.createElementNS(SVG_NAMESPACE, "polyline");
    path.setAttribute("points", points.join(" "));
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", seriesColor(colorIndex));
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("stroke-linecap", "round");
    return path;
}


function buildLegend(keywords) {
    return keywords.map(function buildLegendEntry(keyword, index) {
        const entry = document.createElement("span");
        entry.className = "trends-legend-entry";

        const swatch = document.createElement("span");
        swatch.className = "trends-legend-swatch";
        // The colour is data, not styling, so it is set on the element rather
        // than in the stylesheet, which cannot know the keyword order.
        swatch.style.backgroundColor = seriesColor(index);

        const label = document.createElement("span");
        label.textContent = keyword;

        entry.append(swatch, label);
        return entry;
    });
}


function seriesColor(index) {
    return SERIES_COLORS[index % SERIES_COLORS.length];
}


function horizontalPosition(index, pointCount, box) {
    const drawableWidth = box.width - PADDING_LEFT - PADDING_RIGHT;
    // A single point has no span to spread across, so it sits at the left edge.
    if (pointCount <= 1) {
        return PADDING_LEFT;
    }
    return PADDING_LEFT + (index / (pointCount - 1)) * drawableWidth;
}


function verticalPosition(indexValue, box) {
    const drawableHeight = box.height - PADDING_TOP - PADDING_BOTTOM;
    const clamped = Math.min(Math.max(indexValue, INDEX_MINIMUM), INDEX_MAXIMUM);
    const fraction = (clamped - INDEX_MINIMUM) / (INDEX_MAXIMUM - INDEX_MINIMUM);
    // SVG measures y downward, so a high index sits near the top.
    return PADDING_TOP + (1 - fraction) * drawableHeight;
}
