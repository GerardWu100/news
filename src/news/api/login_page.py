"""Render the sign-in page.

The rest of the browser client is a static single-page app, but the sign-in
page has to carry server-generated values (a one-time form token and an error
message), so it is built here instead of shipped as a static file.

Styles are inline because the response's Content Security Policy allows no
external resources. The colours match ``static/styles.css`` so the two pages
look like one product.
"""

from __future__ import annotations

import html

from fastapi.responses import HTMLResponse

PAGE_TITLE = "Sign in - News Search Engine"

_PAGE_STYLES = """
:root {
  --page-bg: #f1ede4;
  --page-accent: #c15538;
  --page-accent-dark: #913a26;
  --page-ink: #17202e;
  --page-muted: #68707a;
  --panel-solid: #fcf9f2;
  --panel-border: rgba(42, 49, 58, 0.12);
  --error: #b64935;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--page-ink);
  font-family: "Segoe UI", system-ui, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(196, 93, 61, 0.14), transparent 22%),
    radial-gradient(circle at 84% 18%, rgba(36, 84, 156, 0.12), transparent 20%),
    var(--page-bg);
}
.card {
  width: 100%;
  max-width: 25rem;
  padding: 2.2rem;
  border: 1px solid var(--panel-border);
  border-radius: 1.1rem;
  background: var(--panel-solid);
  box-shadow: 0 26px 80px rgba(44, 36, 25, 0.12);
}
.eyebrow {
  margin: 0 0 0.4rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--page-accent);
}
h1 { margin: 0 0 0.4rem; font-size: 1.45rem; line-height: 1.2; }
.subtitle { margin: 0 0 1.6rem; font-size: 0.95rem; color: var(--page-muted); }
label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--page-muted);
}
input {
  width: 100%;
  margin-bottom: 1.1rem;
  padding: 0.7rem 0.85rem;
  font: inherit;
  color: var(--page-ink);
  background: #fff;
  border: 1px solid var(--panel-border);
  border-radius: 0.6rem;
}
input:focus { outline: 2px solid var(--page-accent); outline-offset: 1px; }
button {
  width: 100%;
  padding: 0.8rem;
  font: inherit;
  font-weight: 700;
  color: #fff;
  background: var(--page-accent);
  border: none;
  border-radius: 0.6rem;
  cursor: pointer;
}
button:hover { background: var(--page-accent-dark); }
.message {
  margin-bottom: 1.2rem;
  padding: 0.7rem 0.85rem;
  font-size: 0.9rem;
  color: var(--error);
  background: rgba(182, 73, 53, 0.1);
  border: 1px solid rgba(182, 73, 53, 0.35);
  border-radius: 0.6rem;
}
"""


def render_login_page(
    *,
    message: str,
    form_token: str,
    form_token_id: str,
    headers: dict[str, str],
) -> HTMLResponse:
    """Build the sign-in page.

    Parameters
    ----------
    message : str
        Plain-text error to show above the form, or an empty string. The text
        is escaped here, so callers pass unescaped text.
    form_token : str
        One-time token that the submitted form must return.
    form_token_id : str
        Identifier the server uses to find the stored copy of ``form_token``.
    headers : dict[str, str]
        Response headers, normally from
        :func:`news.web.security.login_page_headers`.

    Returns
    -------
    HTMLResponse
        Complete sign-in page.
    """
    message_block = ""
    if message:
        message_block = f'<p class="message">{html.escape(message)}</p>'

    return HTMLResponse(
        content=f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#f1ede4">
<title>{PAGE_TITLE}</title>
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<style>{_PAGE_STYLES}</style>
</head>
<body>
<main class="card">
<p class="eyebrow">Historical news</p>
<h1>Sign in</h1>
<p class="subtitle">Search results and exports need an account.</p>
{message_block}
<form method="post" action="/login">
<input type="hidden" name="form_token" value="{html.escape(form_token)}">
<input type="hidden" name="form_token_id" value="{html.escape(form_token_id)}">
<label for="username">Username</label>
<input id="username" name="username" type="text" autocomplete="username"
       autocapitalize="none" spellcheck="false" required autofocus>
<label for="password">Password</label>
<input id="password" name="password" type="password"
       autocomplete="current-password" autocapitalize="none"
       spellcheck="false" required>
<button type="submit">Sign in</button>
</form>
</main>
</body>
</html>
""",
        headers=headers,
    )
