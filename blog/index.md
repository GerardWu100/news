---
title: "Historical Market News Search"
description: "Search past market news to practise human forecasts or supply date-limited evidence to an AI-agent backtest."
date: 2026-07-30
image: images/historical-market-news-search.png
categories: ["Quantitative Research", "Artificial Intelligence", "Computer Science"]
---

# Historical Market News Search

This project has two purposes:

1. **Train human market intuition:** stop at a past date, read only the news available then, make a forecast, and reveal the outcome afterward.
2. **Test AI-agent strategies:** give an artificial intelligence (AI) agent the same date-limited news, then send its forecast to a separate backtest.

Repository: [github.com/GerardWu100/news](https://github.com/GerardWu100/news)

![Historical Market News Search browser](images/historical-market-news-search.png)

The front end puts the two uses first, followed by the query, date cutoff, sources, and filters.

## What it can do

Search `semiconductor demand` from July 1 through July 31, select The New York Times and The Guardian, keep English articles, and remove duplicates. The result includes:

- Articles dated inside that window, sorted newest or oldest first.
- One report per source: available, failed, zero matches, article count, and whether another page exists.
- JSON and CSV downloads that preserve the active query and filters.
- A shareable URL that restores the same browser search.

More controls narrow the result by exact phrase, excluded terms, included or excluded domains, article section, New York Times news desk, Guardian tag, and NewsAPI field. Searches can run in the browser, through the `news-search` command-line interface (CLI), or through the HTTP application programming interface (API).

The CLI can collect several pages and export a table, CSV, JSON, JSON Lines, or SQLite. JSON Lines stores one article per line, which makes large results easier for an agent to process.

Google Trends shows relative search interest for the same words and dates. An optional decision date removes later observations before rescaling the chart.

## Sources

- **GDELT Project:** open global news index; no API key.
- **The New York Times Article Search API:** `NYT_API_KEY`.
- **The Guardian Open Platform:** `GUARDIAN_API_KEY`.
- **NewsAPI:** `NEWSAPI_API_KEY`.
- **MediaCloud API:** `MEDIACLOUD_API_KEY` plus selected media collections.
- **ACLED API:** conflict and protest events accessed through OAuth.

The service searches selected sources in parallel and converts their responses into one article format. A failed API does not hide successful results from the others.

## Human workflow

Choose an old earnings date. Search the preceding 30 days. Write down the expected direction, five-day horizon, confidence, and what would prove the view wrong. Only then open the price chart.

Repeating this exercise makes mistakes visible: one memorable headline received too much weight, five copies of one wire story looked like five confirmations, or the forecast changed after the outcome was known.

## AI-agent workflow

For each historical decision date, save the query, returned articles, source reports, model, prompt, and forecast. Trade only after a realistic collection and processing delay. The news service supplies evidence; the outside agent forecasts; the separate backtest handles positions, costs, and returns.

## Roadmap

- **Key asset movement:** show the relevant asset's price during the search window and afterward. Keep the post-cutoff move hidden until the human forecast is saved, and keep it out of AI inputs.
- **Built-in AI summary:** summarize only the returned articles, link every claim to its sources, and save the window, provider failures, model, prompt, and output.
- **Macroeconomic context:** add policy rates, inflation, unemployment, gross domestic product growth, and yield-curve levels for the searched period. Use only figures released by the decision date and preserve historical vintages when later revisions exist.
- **Better search results:** match related terms such as `Fed` and `Federal Reserve`, tolerate misspellings, show the match score, and merge rewritten versions of the same wire story while keeping the earliest article.

Historical Market News Search retrieves and exports the evidence. It does not summarize articles, call a language model, or run the strategy backtest.
