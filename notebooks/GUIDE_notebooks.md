# GUIDE_notebooks

## Part 1 -- Conceptual Explanation

### Purpose

The `notebooks/` folder stores exploratory Jupyter notebooks that sit outside
the importable product package. These notebooks support upstream API
reconnaissance and schema discovery rather than production search behavior.

### Current contents

- `api_explorer/`: provider-specific notebooks for ACLED, GDELT, MediaCloud, and
  Common Crawl. See `notebooks/api_explorer/GUIDE_api_explorer.md`.

## Part 2 -- Code Reference

- `notebooks/api_explorer/`
  - One notebook and one `API_USAGE.md` per provider.
  - Live-fetch artifacts are written to each provider's local `outputs/` folder.
