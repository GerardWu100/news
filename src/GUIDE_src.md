# GUIDE_src

## Purpose

The `src/` folder contains importable Python product code and package-owned
runtime resources. Tests, project documentation, and generated outputs stay
outside `src/`.

## Folder Map

- `news/`: historical multi-source news retrieval package.

## Development Notes

- Use `uv run news-server` to start the local API and frontend server.
- Use `uv run news-search ...` for command-line search and export workflows.
- Keep reusable Python logic under `src/news/`.
