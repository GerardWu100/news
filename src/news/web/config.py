"""Configuration loading helpers for runtime boundaries."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from news.web.paths import config_path


def read_config(path: Path | None = None) -> dict[str, Any]:
    """Read a TOML configuration file.

    Parameters
    ----------
    path : Path | None, optional
        Configuration file path. ``None`` uses the project-root
        ``config.toml``.

    Returns
    -------
    dict[str, Any]
        Parsed TOML mapping. Missing config files return an empty mapping.
    """
    active_path = config_path() if path is None else path
    if not active_path.exists():
        return {}

    with active_path.open("rb") as config_file:
        return tomllib.load(config_file)


def read_frontend_config(path: Path | None = None) -> dict[str, Any]:
    """Return the frontend table from the project configuration."""
    config = read_config(path)
    return config.get("frontend", {})
