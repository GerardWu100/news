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
| Container account | `NEWS_UID`:`NEWS_GID`, unprivileged | Keeps root out of the container and off the mounted directory |
| Root filesystem | read-only, with a `/tmp` in memory | The application writes only to the mounted data directory |
| Privileges | all capabilities dropped, `no-new-privileges` | Nothing here needs any of them |

The mounted `config.toml` is seeded only when
`${HOME}/.containers/news/config.toml` does not exist. Image upgrades therefore
do not overwrite operator changes.

## Start the service

Copy the credential template, set the sign-in account, and fill only the
provider keys you use:

```bash
cp .env.example .env
```

`UI_USERNAME` and `UI_PASSWORD` are required. Without both, the container starts
but refuses every request, and the entrypoint prints a warning saying so. The
optional `UI_USERNAME_2`, `UI_PASSWORD_2`, `UI_USERNAME_3`, and `UI_PASSWORD_3`
add a second and third account; Compose passes all of them to the container. See
`docs/user/SIGN_IN.md` for what the server does with them.

The container serves as an unprivileged account rather than as root, so it must
run as the owner of the mounted directory. Create that directory and record
your own identifiers in `.env`:

```bash
mkdir -p ~/.containers/news
printf 'NEWS_UID=%s\nNEWS_GID=%s\n' "$(id -u)" "$(id -g)" >> .env
```

Without this the container stops on the first boot and prints the exact
commands to run. Docker creates a missing bind-mount directory owned by root,
which an unprivileged container cannot write to.

Compose reads that root `.env` and passes the account and provider settings to
the container. Create the shared network once if the reverse-proxy stack has not
already created it:

```bash
docker network create single
```

Build and start:

```bash
docker compose up --build -d news
docker compose ps
```

Open `http://127.0.0.1:50023` and sign in. The health check requests `/healthz`
inside the container, which needs no account so that a signed-out container is
still reported as healthy.

The mounted data directory also holds the sign-in state: `.ui_credentials.json`
(each account name and its hashed password), `.ui_sessions.json` (remembered
browsers), and `.login_state.json` (failed-attempt counters).

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

The command line signs in with `UI_USERNAME` and `UI_PASSWORD`, the first
browser account, sent as an HTTP Basic header on every request. Compose passes
both to the `news-cli` service; outside Docker they come from `.env`.

For a remote agent, still put a Transport Layer Security (TLS) reverse proxy or
a private virtual private network (VPN) in front of the `news` container and
point `NEWS_SERVER_URL` at that address. The account protects the data, but it
travels in plain text without TLS, and up to three equal accounts are not an
access-control system. Set `security.trust_forwarded_headers = true` in
`config.toml` when a proxy you control sits in front, so failed-attempt limits
count the real client address.

Nothing about the agent's behavior lives in this repository. It calls the
command like any other program and reads the structured output; the
instructions, the model, and the key stay with whoever runs it.

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
