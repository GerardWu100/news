"""Resolve operator-owned files and installed package resources.

Static browser assets ship inside :mod:`news.web`. Configuration and dotenv
files remain operator-owned and are resolved relative to the process working
directory, so an installed wheel never depends on a source checkout.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

CONFIG_ENVIRONMENT_VARIABLE = "NEWS_CONFIG"
CONFIG_FILENAME = "config.toml"
DOTENV_FILENAME = ".env"


def env_path() -> Path:
    """Return the optional dotenv path in the current working directory.

    Returns
    -------
    Path
        Absolute path to ``.env``. The file need not exist.
    """
    return Path.cwd() / DOTENV_FILENAME


def config_path(explicit_path: Path | str | None = None) -> Path | None:
    """Resolve the optional external configuration path.

    Resolution order is an explicit caller path, the ``NEWS_CONFIG``
    environment variable, then ``config.toml`` in the current working
    directory. ``None`` means the packaged defaults should be used.

    Parameters
    ----------
    explicit_path : Path | str | None, optional
        Configuration path supplied by a command-line or application caller.

    Returns
    -------
    Path | None
        Absolute external configuration path, or ``None`` when no external
        file was selected.
    """
    if explicit_path is not None:
        return Path(explicit_path).expanduser().resolve()

    environment_path = os.getenv(CONFIG_ENVIRONMENT_VARIABLE, "").strip()
    if environment_path:
        return Path(environment_path).expanduser().resolve()

    working_directory_path = Path.cwd() / CONFIG_FILENAME
    if working_directory_path.is_file():
        return working_directory_path
    return None


def static_dir() -> Path:
    """Return the installed static-asset directory.

    Returns
    -------
    Path
        Filesystem path to the package-owned HTML, CSS, and JavaScript assets.
    """
    static_resource = resources.files("news.web").joinpath("static")
    return Path(str(static_resource))
