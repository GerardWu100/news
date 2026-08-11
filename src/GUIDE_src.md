# GUIDE_src

## Purpose

The `src/` folder contains importable Python product code and package-owned
runtime resources. Tests, project documentation, and generated outputs stay
outside `src/`.

## Folder Map

- `news/`: historical multi-source news retrieval package.

## Development Notes

- Set `UI_USERNAME` and `UI_PASSWORD` in `.env` before starting anything. Every
  route that returns news data refuses requests without them. Two more accounts
  are optional, through `UI_USERNAME_2`/`UI_PASSWORD_2` and
  `UI_USERNAME_3`/`UI_PASSWORD_3`.
- Use `uv run news-server` to start the local API and frontend server. Add
  `--reload` only during development; `--host` and `--port` control the bind.
- Use `uv run news-trends ...` for search-attention data covering the same
  window as a search. It calls the package directly and needs no running
  server and no account.
- Use `uv run news-search ...` for command-line search and export workflows.
  `NEWS_SERVER_URL` supplies a reusable local or remote API base URL, and the
  same two account settings are sent as an HTTP Basic header. `--direct` skips
  HTTP and therefore needs no account.
- Keep reusable Python logic under `src/news/`.
