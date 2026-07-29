---
name: summarize-news-cli
description: Retrieve historical or current news with this workspace's news-search command and turn the structured CLI results into an evidence-bounded summary. Use when an agent must search a precise publication-date window, call a local or remote Docker-hosted News API through the CLI, summarize returned headlines and provider snippets, compare source coverage, or preserve retrieved evidence for reproducible research. Do not use for unrestricted web research or claims that require full article bodies when the CLI returned only metadata or snippets.
---

# Summarize News with the CLI

Retrieve first, inspect the machine-readable evidence, and summarize only what
the returned records support. Keep the publication window visible because its
inclusive end date is the research information boundary.

## Run the retrieval

Run commands from the repository root. Use JSON for a bounded batch because it
retains both normalized articles and provider execution metadata.

```bash
uv run news-search "central bank policy" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --english \
  --all-pages \
  --max-pages 10 \
  --format json \
  --quiet
```

Add `--sources gdelt,guardian,nyt` only when the user requests those providers
or the server reports them as available. An omitted `--sources` uses every
available provider. Keep the default deduplication unless the user needs raw
cross-provider repetition.

Use one page first for a broad or ambiguous query. Use `--all-pages` only after
the query and filters are precise; retain `--max-pages` as a cost and volume
guardrail. The server rejects windows longer than 366 days, so split a longer
study into non-overlapping windows and label each one.

## Call a remote Docker server

Prefer a private virtual private network (VPN) address or an authenticated
Transport Layer Security (TLS) reverse-proxy URL. Set the endpoint once:

```bash
export NEWS_SERVER_URL="https://news.example.com"
uv run news-search "inflation" \
  --start 2026-06-01 \
  --end 2026-06-30 \
  --format json \
  --quiet
```

An explicit `--server URL` overrides the default. When using the repository's
Dockerized CLI against the server on the same Compose network:

```bash
docker compose run --rm news-cli "inflation" \
  --start 2026-06-01 \
  --end 2026-06-30 \
  --format json \
  --quiet
```

That container defaults to `http://news:8000`. For another protected remote
server, add `-e NEWS_SERVER_URL="https://news.example.com"` before the
`news-cli` service name.

Never invent a remote hostname or expose port 8000 publicly. The application
does not implement user authentication; remote protection belongs at the
private network or reverse-proxy boundary.

## Inspect before summarizing

Read both top-level JSON objects:

- `results` contains normalized article records. Treat `summary` and `content`
  as provider-supplied evidence, not as verified full-article text.
- `meta` records the query, inclusive dates, returned count, removed
  duplicates, requested sources, pagination state, and `source_reports`.

Check for provider errors, unavailable sources, a truncated page range, zero
results, duplicate collapse, missing dates, and thin or empty summaries. If
coverage is weak, refine the query or retrieve another explicitly labeled
window instead of filling gaps from model memory.

## Write the summary

Use this compact structure when the user did not request another format:

1. **Boundary and coverage:** state the query, inclusive dates, providers,
   article count, duplicate count, and provider failures.
2. **Main developments:** synthesize repeated themes in descending importance.
3. **Differences or uncertainty:** note conflicting framing, single-source
   claims, missing context, and ambiguous chronology.
4. **Evidence:** link the most useful returned article URLs and include their
   publication dates and sources.
5. **Limitations:** distinguish headlines/snippets from full-article review and
   state that publication filtering reduces, but does not eliminate,
   look-ahead bias.

Attribute claims to the returned articles. Do not claim consensus merely
because near-duplicate syndications repeat the same report. Do not use facts
after the end date in a point-in-time answer, even if they are known from model
training.

## Preserve reproducibility

For research work, save the raw CLI JSON before analysis and record the command,
server URL, retrieval time, query, date window, filters, providers, and
`source_reports`. Store credentials nowhere in the artifact. Use JSON Lines
(`--format jsonl`) only for streaming article records; it omits the metadata
needed for a coverage audit.
