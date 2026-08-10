---
title: "A News Research Service for Both Humans and AI Agents"
description: "How a small Docker deployment turns a historical news search tool into a reusable browser and command-line service."
date: 2026-07-29
categories:
  - Software
  - AI
---

# A News Research Service for Both Humans and AI Agents

News research has an awkward interface problem. A person wants a browser with
visible dates, source controls, readable headlines, and links worth opening. An
artificial intelligence (AI) agent wants almost the opposite: a stable command,
structured output, clear search details, and no hidden state.

The useful design is to put one search engine behind three small interfaces:

```mermaid
flowchart LR
    P[News sources] --> S[Common search service]
    S --> B[Browser for human research]
    S --> C[CLI for AI agents]
    S --> A[HTTP API for applications]
```

The browser and command-line interface (CLI) then share the same validation,
source adapters, filtering, duplicate removal, and date cutoff. That common
core matters more than the interface: a result inspected by a person and a
result summarized by an agent were produced under the same rules.

## The date is part of the result

For historical research, the end date is not a cosmetic filter. It is the
cutoff: the latest publication date the search is allowed to include.

That restriction helps reduce **look-ahead bias**, which occurs when a
historical decision uses information that was not available at the time. It
does not eliminate the problem. Sources can revise articles, archives can be
incomplete, timestamps may not match the moment information became tradable,
and a large language model (LLM) may know later events from training.

The practical rule is simple: every summary should repeat its query, inclusive
date window, source coverage, result count, and source failures. A polished
paragraph without that search context is less useful than it looks.

## Why Docker helps

The application already runs as an installable Python package. Docker adds an
operational boundary around it:

- Python 3.13 and dependencies are fixed by the image and `uv.lock`.
- Source credentials enter through environment variables rather than the
  image.
- A mounted data directory owns the editable `config.toml`.
- A health check confirms that the configuration endpoint responds.
- `restart: unless-stopped` brings the service back after a host restart.
- The host publishes only `127.0.0.1:50023`, so the API is not accidentally
  exposed to the internet.

The container seeds `${HOME}/.containers/news/config.toml` only on first boot.
This is a small but important detail. Defaults are convenient on day one, while
operator changes survive later image rebuilds.

The Compose service also joins an external network called `single`. An existing
reverse proxy can reach the container on that network without publishing the
application port broadly. Remote access should pass through an authenticated
Transport Layer Security (TLS) proxy or a private virtual private network
(VPN). The news application does not implement its own user accounts, and an
open endpoint could let strangers spend the configured source quotas.

## One CLI, local or remote

The agent-facing interface is the `news-search` command. Locally, its default
server is `http://localhost:8000`. For a remote Docker deployment, the same
command reads `NEWS_SERVER_URL`:

```bash
NEWS_SERVER_URL="https://news.example.com" \
uv run news-search "central bank policy" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --english \
  --all-pages \
  --max-pages 10 \
  --format json \
  --quiet
```

The output contains two objects. `results` holds normalized articles. `meta`
holds the query, dates, page state, duplicate count, requested sources, and a
report for each source. JSON Lines (JSONL), where each line is one JSON record,
is useful for streaming. Full JSON is better for research summaries because it
retains the details needed to judge coverage.

The `--max-pages` option is not mere caution. Broad news queries can create
large, expensive inputs for an LLM. A page limit makes the retrieval budget
visible and prevents an agent from turning a vague request into an unbounded
collection job.

## A local skill turns mechanics into a research habit

The project includes a workspace-only skill named `summarize-news-cli`. A skill
is a short set of operating instructions that an AI coding agent loads when a
matching task appears. Keeping it inside `.agents/skills/` makes the workflow
available in this repository without changing the user's global agent setup.

The skill teaches a sequence rather than a writing style:

1. Retrieve JSON through the CLI.
2. Inspect `meta` before reading the articles.
3. Check source errors, missing dates, duplicate removal, and page navigation.
4. Summarize only claims supported by returned headlines or provider snippets.
5. Link useful evidence and state the date boundary.
6. Preserve the raw JSON and exact command for reproducibility.

This ordering prevents a common agent failure: writing a confident narrative
first and treating the search as decoration afterward. Here, coverage determines
what can responsibly be said.

## What the service still does not prove

The system retrieves news; it does not establish truth, causal impact, or a
profitable trading signal. Repeated syndicated headlines are not independent
confirmation. Provider snippets are not full-article review. Publication dates
are not guaranteed tradability timestamps. Deduplication is useful for input
quality, but it can also hide how widely one wire story was republished.

Those limitations suggest the next layer of work:

- archive the raw response beside every generated summary;
- record the model and prompt used for the summary;
- lag any derived signal until it could realistically be acted on;
- test sensitivity to provider choice and query wording;
- keep market returns and backtests outside the retrieval service.

The larger lesson is architectural. Human research and agent research do not
need separate data systems. They need a shared, inspectable retrieval boundary
and interfaces designed for their different ways of working.
