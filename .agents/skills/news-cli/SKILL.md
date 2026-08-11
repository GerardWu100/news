---
name: news-cli
description: Retrieve news published inside an exact historical date window, and search-attention data for the same window, by calling the news-search and news-trends commands against a local or remote News Search Engine server. Use when a task needs news limited to a publication-date window, a point-in-time view of what was reported, a coverage check across providers, or public search interest during those same dates. Do not use for unrestricted web research, for claims needing full article bodies when only headlines and snippets were returned, or to write a summary of the news unless the user asks for one.
---

# Retrieve News Through the CLI

This project retrieves news published inside an exact date window. Its purpose
is to show what was reported at the time, without letting later coverage leak
in. Your job is retrieval and reporting the records: run the command, check
what actually came back, and hand over the results.

**Do not summarize the news unless the user asks for a summary.** The default
deliverable is the retrieved records plus an honest account of coverage. When a
summary is asked for, follow the rules in the last section.

## Setup: how to invoke the commands

Two commands exist: `news-search` for articles and `news-trends` for search
attention. How you call them depends on where you are:

- Inside a checkout of this project, prefix with `uv run`, as in
  `uv run news-search ...`.
- With the package installed elsewhere (`uv tool install` or `pip install`),
  call `news-search` directly.

If `news-search` is not found and there is no checkout to run from, say so
rather than guessing at a path. Every example below omits the prefix; add
`uv run` when you are working inside the project.

## Setup: server address and sign-in

The server refuses every request that returns news unless it is signed in. Two
settings do it:

```bash
export NEWS_SERVER_URL="https://news.example.com"
export UI_USERNAME="the-account-name"
export UI_PASSWORD="the-account-password"
```

`news-search` sends that account as an HTTP Basic header on every request.
`--server URL` overrides `NEWS_SERVER_URL` for one call.

Rules that matter:

- Never invent a hostname, an account name, or a password. If the user has not
  given you the address and the credentials, ask for them.
- A reply saying the sign-in details were rejected means the account name or
  password does not match the one the server was started with. Ask; never guess
  other values.
- Never write the password into a file, a saved artifact, a commit, or your
  visible output.
- The password travels in plain text without encryption. If the address is
  plain `http://` and not on the local machine or a private network, say so
  before sending credentials to it.

Check the server is reachable before a long retrieval:

```bash
curl -s "$NEWS_SERVER_URL/healthz"
```

That route needs no account and answers `{"status":"ok"}`.

## Retrieve articles

```bash
news-search "central bank policy" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --english \
  --format json \
  --quiet
```

Both dates are inclusive, and the end date is the information boundary: nothing
published after it is returned.

Options worth knowing:

| Option | Use it when |
|---|---|
| `--sources gdelt,guardian,nyt` | The user names providers. Omitting it uses every available one. |
| `--all-pages --max-pages 10` | The query is already precise. Keep `--max-pages` as a volume guard. |
| `--format json` | Default choice. Keeps both the articles and the coverage metadata. |
| `--format jsonl` | Streaming article records only. It drops the metadata, so never use it for a coverage check. |
| `--export csv\|json\|sqlite -o PATH` | The user wants a file to keep. |
| `--exact-phrase`, `--exclude`, `--domain` | Narrowing a noisy result set. |

Sequence that avoids waste: run one page first for a broad or vague query, look
at what came back, then add `--all-pages` once the query and filters are right.

The server rejects windows longer than 366 days. Split a longer study into
non-overlapping windows and label each one separately; do not silently merge
them.

## Check coverage before reporting anything

The JSON has two top-level objects, and `meta` is the one that decides whether
the results can be trusted.

- `results` holds the article records. Treat `summary` and `content` as
  provider-supplied text, not as a verified full article.
- `meta` holds the query, the inclusive dates, the returned count, duplicates
  removed, which sources were requested, pagination state, and
  `source_reports`.

Read `meta` first, every time. Specifically look for:

1. **Failed sources.** `source_reports` names each provider, whether it was
   available, how many rows it returned, and any error. Two providers timing
   out looks exactly like a quiet news week if you skip this.
2. **Zero results.** Report it as "nothing was returned for this query and
   window", never as "nothing happened".
3. **More pages.** `has_more` true means you saw part of the result.
4. **Duplicates removed.** Repeated syndications of one report are not several
   independent confirmations.
5. **Missing dates or empty summaries.** Some providers return thin records.

If coverage is weak, say so and offer to widen the query or retrieve another
labelled window. Do not fill the gap from your own knowledge.

## Retrieve search attention for the same window

`news-trends` returns how much the public searched for the same keywords during
the same dates. Articles say what was published; this says what people were
looking for.

```bash
news-trends '"central bank"' \
  -s 2026-01-01 \
  -e 2026-01-31 \
  --geo US \
  --format json
```

It calls the package directly, so it needs no server and no account. It takes
the same query string as `news-search`, then reduces it to plain terms because
the upstream source accepts no operators and at most five keywords: boolean
operators and excluded terms are dropped, repeats are collapsed, and
double-quoted runs stay whole.

**Quote phrases twice.** The inner double quotes are what make a phrase one
keyword, so wrap them in single quotes for the shell:

| What you type | Keywords measured |
|---|---|
| `news-trends "central bank"` | `central`, `bank` — two separate words |
| `news-trends '"central bank"'` | `central bank` — one phrase |

The first form quietly measures something else and spends two of the five
keyword slots. Check the `keywords` field in the output against what you meant
before using the numbers.

**Read the values correctly or do not use them.** They are a relative index
from 0 to 100, never search counts. The value 100 is the busiest point inside
the window that was requested, and everything else is divided by that same
peak. Three consequences:

- Two series fetched over different windows are not comparable. The same day
  can read 100 or 30 depending on how far past it the request reached.
- A 0 can mean the term was too rare for the source to report, not that nobody
  searched it.
- Because the divisor is the peak of the whole window, a value on an early date
  already reflects a spike that had not happened yet. For a point-in-time
  question, pass `--as-of YYYY-MM-DD`: it drops the later points and rescales
  to the highest value up to that date.

```bash
news-trends "bitcoin" -s 2017-01-01 -e 2017-09-15 --as-of 2017-01-05 --geo US
```

Always report the window and the anchor date alongside the numbers. Without
them the values mean nothing.

## Keep the retrieval reproducible

For anything the user will rely on later, save the raw JSON before you work on
it and record the command, the server address, the retrieval time, the query,
the date window, the filters, the providers, and `source_reports`. Keep the
credentials out of every saved artifact.

## If a summary is requested

Only when the user explicitly asks. Then:

- State the query, the inclusive dates, the providers, the article count, and
  any provider failures before anything else.
- Attribute every claim to a returned article, with its date and source.
- Do not treat repeated syndications of one report as agreement.
- Do not use anything you know that happened after the end date, even if you
  are confident about it. The window is the point.
- Separate what the headlines and snippets support from what would need the
  full articles.
