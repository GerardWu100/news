# Docker deployment

The Docker setup uses a small Python 3.13 image built with `uv`, operator-owned
persistent settings, Toronto time, automatic restart, loopback-only host
publishing, and an external reverse-proxy network named `single`.

## Defaults

| Setting | Default | Reason |
|---|---|---|
| Container port | `8000` | Matches the application server |
| Host address and port | `127.0.0.1:50023` | Avoids public exposure and the podcast service’s `50022` port |
| Time zone | `America/Toronto` | Matches the operator’s local time |
| Restart policy | `unless-stopped` | Restarts after failure or host reboot |
| Persistent data | `${HOME}/.containers/news` | Keeps settings outside the image |
| Docker network | external `single` | Lets an existing reverse proxy reach the container |
| Browser defaults | English; Guardian and NYT selected | Copied from `config.toml` on first boot |

The mounted `config.toml` is seeded only when
`${HOME}/.containers/news/config.toml` does not exist. Image upgrades therefore
do not overwrite operator changes.

## Start the service

Copy the credential template and fill only the provider keys you use:

```bash
cp .env.example .env
```

Compose reads that root `.env` and passes the provider settings to the
container. Create the shared network once if the reverse-proxy stack has not
already created it:

```bash
docker network create single
```

Build and start:

```bash
docker compose up --build -d news
docker compose ps
```

Open `http://127.0.0.1:50023`. The health check requests `/api/config` inside
the container.

Useful commands:

```bash
docker compose logs -f news
docker compose restart news
docker compose down
```

`docker compose down` removes the container and its Compose network attachment.
It does not delete `${HOME}/.containers/news`.

## Call the server from an AI agent

The `news-search` command is the agent-facing client. Set a remote server
address with `NEWS_SERVER_URL`, or pass `--server` for one call:

```bash
NEWS_SERVER_URL="https://news.example.com" \
uv run news-search "central bank" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --all-pages \
  --max-pages 10 \
  --format json \
  --quiet
```

The Dockerized CLI can call the server by its Compose service name:

```bash
docker compose run --rm news-cli "central bank" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --format json \
  --quiet
```

Its in-network default is `http://news:8000`. To use it against another server:

```bash
docker compose run --rm \
  -e NEWS_SERVER_URL="https://news.example.com" \
  news-cli "central bank" \
  --start 2026-01-01 \
  --end 2026-01-31 \
  --format json \
  --quiet
```

For a remote agent, put an authenticated Transport Layer Security (TLS) reverse
proxy or a private virtual private network (VPN) in front of the `news`
container and point `NEWS_SERVER_URL` at that address. The FastAPI application
has no user-authentication layer. Do not publish port 8000 or change the host
bind to `0.0.0.0` on an internet-facing machine without a separate access
control layer; otherwise strangers could consume the configured provider
quotas.

The workspace-local skill at `.agents/skills/summarize-news-cli/SKILL.md`
teaches agents to retrieve, check, and summarize the structured result without
bringing later information into a historical study.

## Configuration precedence

Inside Docker, `NEWS_CONFIG=/data/config.toml`, so the persistent file wins.
Outside Docker, the server resolves settings in this order:

1. `news-server --config PATH`
2. `NEWS_CONFIG`
3. `config.toml` in the current directory
4. packaged defaults

Server binding is separately configurable:

```bash
uv run news-server --host 127.0.0.1 --port 8000 --reload
```

Use `--reload` only for local development.
