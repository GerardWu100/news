# Sign-in and security

Every route that returns news data requires an account. The sign-in page,
stylesheet, icon, browser script modules, and `/healthz` check stay open. The
search and documentation HTML cannot be fetched through `/static`; their only
routes require an account.

## Set the accounts

1. Copy the template and edit it:

   ```bash
   cp .env.example .env
   ```

2. Set the first account:

   ```ini
   UI_USERNAME=analyst
   UI_PASSWORD=a-password-you-choose
   ```

3. Start or restart the server.

On startup the server hashes each password, verifies the hash against the
password it just hashed, and writes the account names plus their hashes to
`.ui_credentials.json` in the data directory. The startup log says which of the
two happened:

```text
INFO: Hashed the sign-in passwords for 'analyst' into /data/.ui_credentials.json and passed the hash self-test.
INFO: Sign-in credentials for 'analyst' verified against /data/.ui_credentials.json.
```

You never run a hashing command. To change a password, edit `.env` and restart;
the hash is rewritten and every remembered browser is signed out.

If `UI_USERNAME` or `UI_PASSWORD` is missing, the server starts but refuses
every request and removes any stored account, so a broken configuration fails
closed rather than open.

## Up to three accounts

Two more accounts are available so separate people can have separate passwords.
The extra slots repeat the same two settings with a number added:

```ini
UI_USERNAME=analyst
UI_PASSWORD=a-password-you-choose
UI_USERNAME_2=colleague
UI_PASSWORD_2=another-password
UI_USERNAME_3=
UI_PASSWORD_3=
```

Rules the server applies at startup:

- A slot with both values set becomes an account; a slot left blank is skipped,
  and slots need not be filled in order.
- A slot with only one of the two values set is ignored and logged as a warning,
  because half an account cannot sign in.
- Two slots may not share an account name; the later one is ignored and logged,
  because it could never be reached.
- Every account opens every route. There are no roles, owners, or per-account
  permissions here.
- Adding, removing, or changing any account signs out every remembered browser
  on the next restart.

Nothing else changes: sign-in, the failed-attempt limit, and the sessions
described below work the same whether one account is configured or three.

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

Both check the same set of accounts. The command line reads `UI_USERNAME` and
`UI_PASSWORD`, the first account, so nothing extra is configured:

```bash
uv run news-search "central bank" --start 2026-01-01 --end 2026-01-31
```

`news-search --direct` skips HTTP entirely and calls the package in process, so
it needs no sign-in.

A password check is deliberately slow, so an accepted `Authorization` header is
remembered by digest for five minutes. Only the digest is kept, never the
password. This keeps a command that pages through results from paying the full
hashing cost on every request. Writing a new account file empties that memory,
so a header accepted under the old password stops working at once rather than
five minutes later.

## Sessions

- A session lasts 30 days.
- Sessions live in `.ui_sessions.json` and survive a server restart.
- The file stores the session identifier, its creation time, the account name
  that signed in, and the sign-out token for that session. It is not tied to
  the address that signed in.
- Every check reads the file under a lock rather than a copy held in memory, so
  a browser that signs in through one worker process is recognized by all of
  them.
- A browser that opens `/login` with a live session goes straight to the app.
- Changing any account name or password deletes the file, signing everyone out.

## Slowing down guessing

Failed attempts are counted per client address in `.login_state.json`. After
5 failures within 10 minutes the address is refused for 15 minutes. Failures
through the sign-in form and through the `Authorization` header count toward
the same limit, so the header is not a way around it.

A record is removed once its window has passed and its ban has expired, so the
file stays proportional to the addresses currently failing rather than growing
by one row for every address ever seen.

A wrong account name and a wrong password produce the same message and take the
same time, so a response does not reveal which half was wrong.

## Protection against unwanted form submissions

Cross-Site Request Forgery (CSRF) is when another site makes a signed-in
browser submit a form to this server. Both forms here carry a random token that
the server issued and remembers:

- The sign-in form gets a one-time token that expires after 10 minutes and
  cannot be replayed. The number of tokens waiting to come back is capped, so
  requesting sign-in forms in a loop cannot exhaust storage. Tokens are kept
  in `.login_form_tokens.json` under a lock, so the page and submission may
  reach different worker processes.
- The sign-out button gets a token tied to the session, fetched by the page
  from `/api/session`. It is stored with the session, so the page and the
  submission need not reach the same worker process.

## Browser hardening

Every response carries `Referrer-Policy: same-origin`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and a Content
Security Policy. Anything that is not an allowed public asset under `/static` also
carries `Cache-Control: no-store`, so search results are never written to a
shared cache.

Two policies are used, because the two HTML pages load different things:

| Response | Content Security Policy |
|---|---|
| Sign-in page | Nothing external; its stylesheet is inline |
| Search page | Its own scripts and stylesheet, plus the linked web fonts |
| Search results, exports, redirects | Nothing at all |

Neither page allows inline scripts or inline styles, so markup injected into an
article title has nothing to execute. `Strict-Transport-Security` is sent only
on connections that already arrived over HTTPS, because promising HTTPS over a
plain connection would lock a local deployment out of its own server.

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

Set it to `true` when a reverse proxy you control, such as a Cloudflare Tunnel,
sits in front. It then reads the real client address from `CF-Connecting-IP` or
`X-Forwarded-For`, and marks the session cookie `Secure` when
`X-Forwarded-Proto` or `CF-Visitor` reports HTTPS.

The setting alone is not enough to be believed. The machine that actually
opened the connection must also be on the loopback interface or a private
network, which is where a reverse proxy in front of this server lives. A caller
arriving straight from a public address is never believed, even while the
setting is on, so a forged header cannot spend another client's failed-attempt
budget.

Leave it `false` when no proxy is in front.

## What this is not

- At most three accounts, no second factor, no per-account permissions. The
  accounts separate people, not rights.
- An admin surface for personal use, not a multi-user public application.
- Anyone who can read the data directory can read the plain passwords in `.env`.
