"""Configuration loading helpers for runtime boundaries."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from news.web.paths import config_path


def read_config(path: Path | str | None = None) -> dict[str, Any]:
    """Read a TOML configuration file.

    Parameters
    ----------
    path : Path | str | None, optional
        Explicit configuration file. ``None`` applies the standard external
        lookup and falls back to the packaged defaults.

    Returns
    -------
    dict[str, Any]
        Parsed TOML mapping.
    """
    active_path = config_path(path)
    if active_path is not None:
        with active_path.open("rb") as config_file:
            return tomllib.load(config_file)

    default_resource = resources.files("news.web").joinpath("default_config.toml")
    with default_resource.open("rb") as config_file:
        return tomllib.load(config_file)


def read_frontend_config(path: Path | str | None = None) -> dict[str, Any]:
    """Return the frontend table from the project configuration."""
    config = read_config(path)
    return config.get("frontend", {})
