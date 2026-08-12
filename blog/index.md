---
title: "Historical Market News Search"
description: "A historical news tool with two purposes: train human market intuition and supply date-limited evidence for AI-agent strategy backtests."
date: 2026-08-12
image: images/historical-market-news-search.png
categories: ["Quantitative Research", "Artificial Intelligence", "Computer Science"]
---

# Historical Market News Search

This project has two purposes:

1. **Train human market intuition.** A person chooses a past date window, reads only the news available inside it, writes down a market forecast, and checks the later outcome.
2. **Supply news for AI-agent backtests.** An artificial intelligence (AI) agent receives the same date-limited evidence, produces a forecast, and passes that forecast to a separate strategy backtest.

The source code and setup instructions are in the [Historical Market News Search GitHub repository](https://github.com/GerardWu100/news).

![Historical Market News Search browser](images/historical-market-news-search.png)

The front end states both purposes at the top. The user then chooses a topic, start date, end date, news sources, language, and filters.

## What the project does

Historical Market News Search retrieves articles published inside an inclusive date window. The same search is available through a browser, the `news-search` command-line interface (CLI), and an HTTP application programming interface (API).

The service performs the data work needed before either research workflow:

- Search several providers in parallel.
- Convert different provider responses into one article format.
- Apply date, language, phrase, term, domain, section, and source filters.
- Remove obvious duplicate URLs and same-day copies when requested.
- Return one status report per source, including failures and zero-result searches.

Results can be downloaded as CSV or JSON in the browser. The CLI also supports a readable table, JSON Lines, and SQLite. JSON Lines stores one JSON record per line, which is convenient when an agent processes many articles.

The project retrieves and exports evidence. It does not summarize articles, call a language model, calculate returns, create positions, or run a backtest.

## News sources and APIs

The service connects to six news providers:

- **GDELT Project:** an open global news index that does not require an API key.
- **The New York Times Article Search API:** a publisher archive accessed with `NYT_API_KEY`.
- **The Guardian Open Platform and NewsAPI:** publisher and news-aggregation APIs accessed with `GUARDIAN_API_KEY` and `NEWSAPI_API_KEY`.
- **MediaCloud API:** a research news database accessed with `MEDIACLOUD_API_KEY` and configured media collections.
- **ACLED API:** conflict and protest event data accessed through OAuth, an authorization standard used to obtain a temporary bearer token.

Google Trends is separate from the article providers. It reports relative search interest for the same query and dates through the browser, the `news-trends` command, and `GET /api/trends/interest`.

Each provider covers a different part of the news record. Searching more sources improves coverage, but it does not remove geographic, editorial, language, or archive bias. The response keeps the source attached to every article so later research can measure those differences.

## Purpose one: train human market intuition

Market intuition is the ability to form a clear, testable view from incomplete information. The front end turns that skill into a repeatable exercise:

1. Choose a company, market topic, and historical date window.
2. Read the returned articles and check which sources succeeded or failed.
3. Record a forecast, its time horizon, confidence, and the evidence that would invalidate it.
4. Reveal the later market outcome and score the forecast without rewriting the original view.

For example, a researcher can stop on a past earnings date, review only the preceding 30 days of news, and forecast the next five trading days before opening the price chart. Repetition exposes habits that normal retrospective reading hides, such as overweighting one vivid story or treating several copies of the same report as independent confirmation.

Google Trends adds a second view of the information environment. Articles show what publishers released; search interest shows what the public was looking for during the same period.

## Purpose two: supply an AI-agent strategy backtest

The machine workflow uses the CLI or HTTP API instead of the browser. At each historical decision date, an outside AI agent receives only the allowed news window. The agent makes a forecast, while a separate backtest applies the trading rules and measures what happened afterward.

A valid test should save the query, dates, raw response, source reports, model, prompt, and forecast for every decision. It should also delay any simulated trade until the news could realistically have been collected, processed, and acted upon.

Keeping retrieval separate from the agent and backtest makes failures easier to diagnose. A missing article is a data problem. An unsupported forecast is an agent problem. An impossible fill or missing transaction cost is a backtest problem.

## What the date cutoff cannot guarantee

The end date reduces look-ahead bias, which means accidentally using future information in a historical decision. It cannot remove that risk by itself.

An article may have been edited after publication. An archive may be incomplete. A provider's date may not equal the time when a trader could act. A language model may know the later outcome from its training data. Google Trends also rescales every request relative to its own peak, so the optional decision date removes later observations and rebases the remaining values to the information available by that date.

These limits matter most for the AI workflow. A serious backtest must preserve each historical response, keep the final evaluation period untouched, record every prompt or strategy variation, and model a realistic delay between information and execution.

Historical Market News Search provides the dated news, source coverage, filters, and exports needed for those two workflows. The human or AI agent forms the forecast; the project keeps the evidence window visible and reproducible.
