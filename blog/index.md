---
title: "Read the News Before the Outcome"
description: "A historical news service with two jobs: train human market intuition and provide point-in-time inputs for AI-agent backtests."
date: 2026-08-12
image: images/historical-news-interface.png
categories: ["Quantitative Research", "Artificial Intelligence", "Computer Science"]
---

# Read the News Before the Outcome

Most market research starts with a hidden advantage: we already know what happened. Once the outcome is visible, old headlines seem more informative and the warning signs seem more obvious than they did in real time.

I built [Historical News](https://github.com/GerardWu100/news) to remove some of that advantage. It searches a fixed historical window across several news archives, places every result behind an explicit cutoff date, and exposes the same search through a browser, a command-line interface (CLI), and an HTTP application programming interface (API).

The project has two jobs. The front end is a practice environment for a human who wants to develop market intuition. The machine interface supplies date-bounded evidence to an artificial intelligence (AI) agent that predicts a later market outcome inside a walk-forward backtest. The service does not make the prediction or run the backtest; it controls one of their most important inputs.

![Historical News browser interface](images/historical-news-interface.png)

The browser keeps the research rule on screen: choose the cutoff before forming a view. It also makes the active dates, selected sources, and duplicate-removal setting visible.

## One retrieval layer, two research workflows

The common layer searches GDELT, MediaCloud, ACLED, The New York Times, The Guardian, and NewsAPI. Provider responses are converted into one article format, filtered, optionally deduplicated, sorted, and returned with a report for every requested source. Google Trends adds a separate measure of what people were searching for during the same window.

**Human path:** historical sources → date-bounded retrieval → browser exercise → human market view → reveal the later outcome.

**AI path:** historical sources → date-bounded retrieval → CLI or HTTP API → AI-agent prediction → separate walk-forward backtest.

This shared retrieval layer matters. A person and an agent can inspect the same query, dates, articles, source failures, and duplicate count. Differences in their conclusions then come from the research process rather than from two undocumented data pipelines.

The core search path is deliberately plain:

```python
raw_articles, source_reports = await executor(
    source_options,
    request.source_names,
)

filtered_articles = apply_post_filters(raw_articles, request)

if request.deduplicate:
    processed_articles = deduplicate_articles(filtered_articles)
else:
    processed_articles = filtered_articles

sorted_articles = sort_articles(processed_articles, request.sort_order)
```

The `source_reports` output is as important as the article list. Zero results from a working source and zero results because a source failed are different observations. A backtest that treats them as the same can turn a data outage into a trading signal.

## What the current implementation includes

The research idea only works if the service is dependable enough for both interactive and repeated use. The current implementation therefore includes the operational pieces around the search itself:

- The six providers run in parallel. A failed provider does not erase successful results from the others, and every requested source receives its own status report.
- The browser, CLI, and HTTP API use the same validation, filtering, deduplication, sorting, and normalized article schema. Identical requests already in progress share one provider search, while a short-lived cache reduces repeated use of provider quotas.
- Every route that returns news requires an account. The browser uses a session cookie, the CLI uses HTTP Basic authentication, and file locks keep sessions and failed-attempt limits consistent across server processes.
- Results can be downloaded as CSV or JSON from the browser and exported as tables, CSV, JSON, JSON Lines, or SQLite through the CLI. JSON Lines means one JSON record per line, which is useful for streaming large result sets.
- The package runs on Python 3.13 and can be installed with `uv` or deployed with Docker. The supplied Compose setup publishes only to the host loopback interface on port 50024, leaving public access to a separate Transport Layer Security (TLS) proxy or private network.

These are not separate versions of the product. They are different entry points into the same retrieval rules, which is what makes a browser exercise reproducible later from code.

## Function one: train human market intuition

Here, **market intuition** means the ability to form a testable view from incomplete information: what matters, what the market may already expect, which evidence conflicts, and what would change the view. It is not a claim that instinct should replace measurement.

A useful exercise takes four steps:

1. Pick a company, topic, and historical cutoff date.
2. Read only articles dated inside the allowed window and inspect which sources answered.
3. Write down a prediction, confidence level, time horizon, and evidence that would prove it wrong.
4. Reveal the later price path or economic release, score the prediction, and record what was missed.

For example, a researcher could stop on an earnings date, search the preceding 30 days, and predict the next five trading days before opening the chart. Repeating the exercise creates feedback. It also exposes habits that ordinary retrospective reading hides: overweighting one vivid article, mistaking repeated wire copies for independent confirmation, or changing the forecast after seeing the result.

The front end supports this exercise directly. The cutoff is labelled as part of the search, advanced filters remain available when a broad query is noisy, and the result page reports source-level coverage. The Google Trends panel adds another question: did public attention change before the news narrative did?

## Function two: supply an AI-agent backtest

The second workflow replaces the browser with the CLI or HTTP API. At each historical decision date $d$, an outside agent receives only articles with publication dates no later than $d$. It produces a forecast for a later horizon, and a separate backtest records the signal, applies an execution delay, and measures the subsequent return.

A minimal walk-forward loop is:

1. Set decision date $d$ and retrieve the allowed news window ending at $d$.
2. Save the raw response, query, source reports, agent model, and prompt.
3. Ask the agent for a prediction that includes direction, horizon, confidence, and invalidating evidence.
4. Convert the prediction into a position only after a realistic delay, then value it with later prices.
5. Move $d$ forward and repeat without changing earlier outputs.

This design can test questions such as whether an agent can predict the next day's market direction from the previous week's news, or whether its confidence contains information about the size of the later move. The exact target, asset universe, transaction costs, and evaluation metric belong in the backtest, not in the retrieval service.

That separation is intentional. If retrieval, prompting, portfolio rules, and performance accounting live in one opaque process, a strong result is hard to diagnose. With a fixed retrieval boundary, I can test the agent while keeping the historical evidence inspectable.

## Google Trends needs its own cutoff treatment

Google Trends reports a relative index from 0 to 100, not a search count. Its scaling can introduce a less obvious form of look-ahead bias.

Define $v_t$ as the unobserved search volume at time $t$. Let the requested window be $W=[s,e]$, where $s$ is the start date and $e$ is the end date. Let $m_W=\max_{u \in W} v_u$ be the highest volume anywhere in that window. Google reports the index $I_t$:

$$
I_t = 100 \times \frac{v_t}{m_W}.
$$

If a decision occurs at date $d$, values after $d$ were not yet known. Define $m_d=\max_{u \in [s,d]}v_u$, the maximum available by the decision date. The service drops later observations and rebases the observed index:

$$
\begin{aligned}
\widetilde{I}_t
&= 100 \times \frac{I_t}{\max_{u \in [s,d]} I_u} \\
&= 100 \times \frac{100v_t/m_W}{100m_d/m_W} \\
&= 100 \times \frac{v_t}{m_d}, \qquad t \le d.
\end{aligned}
$$

Here, $\widetilde{I}_t$ is the index rescaled using only the information available by $d$. The second line substitutes the definition of $I_t$ into both the numerator and denominator. The common full-window scale $m_W$ cancels in the third line.

This correction preserves the relative shape of the values that Google returned. It cannot recover precision already lost when Google rounded small values, so fetching a window that ends near $d$ is still safer.

## What the cutoff does not solve

Publication dates reduce look-ahead bias; they do not prove that every input was tradable at that time. An article can be revised after publication. Archives can be incomplete. Provider timestamps can use different meanings. A language model may already know the later event from its training data.

For an investable claim, the backtest must also keep observation time, retrieval time, decision time, order time, and fill time separate. It needs an untouched chronological test period, realistic costs, and a record of every prompt or strategy variation tried. Otherwise, the process can overfit the historical sample even when every article passes the date filter.

Historical News provides the input boundary and the audit trail needed to start that work. Its browser turns market history into deliberate practice for a person. Its machine interfaces make the same evidence reusable for an agent. The source code and setup instructions are in the [GitHub repository](https://github.com/GerardWu100/news).
