# Sign-in and security

Every route that returns news data requires an account. Three things stay open,
because none of them reveal search results: the sign-in page, the browser's own
static files under `/static`, and the `/healthz` check the container uses.

## Set the account

1. Copy the template and edit it:

   ```bash
   cp .env.example .env
   ```

2. Set both values:

   ```ini
   UI_USERNAME=analyst
   UI_PASSWORD=a-password-you-choose
   ```

3. Start or restart the server.

On startup the server hashes the password, verifies the hash against the
password it just hashed, and writes the account name plus the hash to
`.ui_credentials.json` in the data directory. The startup log says which of the
two happened:

```text
INFO: Hashed the login password for 'analyst' into /data/.ui_credentials.json and passed the hash self-test.
INFO: Login credentials for 'analyst' verified against /data/.ui_credentials.json.
```

You never run a hashing command. To change the password, edit `.env` and
restart; the hash is rewritten and every remembered browser is signed out.

If `UI_USERNAME` or `UI_PASSWORD` is missing, the server starts but refuses
every request and removes any stored account, so a broken configuration fails
closed rather than open.

## How the password is stored

The stored value looks like this:

```text
pbkdf2_sha256$600000$<salt>$<derived key>
```

- **PBKDF2** (Password-Based Key Derivation Function 2) turns the password into
  a fixed-length key by repeating a keyed hash. Repeating it 600,000 times is
  the point: each guess by someone who steals the file costs real time.
- The **salt** is a random value stored in the clear. It makes two identical
  passwords hash to different values, so a precomputed table of common password
  hashes is useless.
- Comparison uses a constant-time check, so response timing does not leak how
  much of a wrong value was correct.

The plain password still sits in `.env` on disk. That is a deliberate
convenience trade-off. `.env` and `.ui_credentials.json` are written with
owner-only (600) permissions; keep the data directory private.

## Two ways to sign in

| Caller | Method | What it sends |
|---|---|---|
| Browser | Sign-in form | A session cookie, set once and kept for 30 days |
| `news-search` and other programs | HTTP Basic | `UI_USERNAME` and `UI_PASSWORD` as an `Authorization` header on every request |

Both check the same account. The command line reads the same two settings from
`.env`, so nothing extra is configured:

```bash
uv run news-search "central bank" --start 2026-01-01 --end 2026-01-31
```

`news-search --direct` skips HTTP entirely and calls the package in process, so
it needs no sign-in.

A password check is deliberately slow, so an accepted `Authorization` header is
remembered by digest for five minutes. Only the digest is kept, never the
password. This keeps a command that pages through results from paying the full
hashing cost on every request.

## Sessions

- A session lasts 30 days.
- Sessions live in `.ui_sessions.json` and survive a server restart.
- The file stores only the session identifier and its creation time. It is not
  tied to the address that signed in.
- A browser that opens `/login` with a live session goes straight to the app.
- Changing the account name or password deletes the file, signing everyone out.

## Slowing down guessing

Failed attempts are counted per client address in `.login_state.json`. After
5 failures within 10 minutes the address is refused for 15 minutes. Failures
through the sign-in form and through the `Authorization` header count toward
the same limit, so the header is not a way around it.

A wrong account name and a wrong password produce the same message and take the
same time, so a response does not reveal which half was wrong.

## Protection against unwanted form submissions

Cross-Site Request Forgery (CSRF) is when another site makes a signed-in
browser submit a form to this server. Both forms here carry a random token that
the server issued and remembers:

- The sign-in form gets a one-time token that expires after 10 minutes and
  cannot be replayed.
- The sign-out button gets a token tied to the session, fetched by the page
  from `/api/session`.

## Browser hardening

Sign-in responses carry `Cache-Control: no-store`, `Referrer-Policy:
same-origin`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and a
Content Security Policy that allows no external resources.

The 401 responses deliberately omit the `WWW-Authenticate` header. With it, a
browser would show its own native password box on top of the app's sign-in
page. The command line sends its header without waiting to be asked, so nothing
is lost.

## Behind a reverse proxy

`config.toml` controls whether proxy headers are believed:

```toml
[security]
trust_forwarded_headers = false
```

Set it to `true` only when a reverse proxy you control, such as a Cloudflare
Tunnel, sits in front. It then reads the real client address from
`CF-Connecting-IP` or `X-Forwarded-For`, and marks the session cookie `Secure`
when `X-Forwarded-Proto` or `CF-Visitor` reports HTTPS.

Leave it `false` when clients reach the server directly. Otherwise any client
can forge those headers and spend another client's failed-attempt budget.

## What this is not

- One shared account, no second factor, no per-user permissions.
- An admin surface for personal use, not a multi-user public application.
- Anyone who can read the data directory can read the plain password in `.env`.
