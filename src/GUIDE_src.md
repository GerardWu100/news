# GUIDE_src

## Purpose

The `src/` folder contains importable Python product code and package-owned
runtime resources. Tests, project documentation, and generated outputs stay
outside `src/`.

## Folder Map

- `news/`: historical multi-source news retrieval package.

## Development Notes

- Use `uv run news-server` to start the local API and frontend server. Add
  `--reload` only during development; `--host` and `--port` control the bind.
- Use `uv run news-search ...` for command-line search and export workflows.
  `NEWS_SERVER_URL` supplies a reusable local or remote API base URL.
- Keep reusable Python logic under `src/news/`.
