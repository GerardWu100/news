"""Find operator-owned files and installed package resources.

Browser files ship inside :mod:`news.web`. Operator-owned files live in the
data directory, which is ``NEWS_DATA_DIR`` when set and the process working
directory otherwise, so an installed wheel never needs a source checkout.

Data-directory files
--------------------
``.env``
    Credentials, including the browser login account name and password.
``.ui_credentials.json``
    Account name and hashed password written by startup.
``.ui_sessions.json``
    Remembered browser sessions.
``.login_state.json``
    Failed-login counters used to slow down password guessing.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

CONFIG_ENVIRONMENT_VARIABLE = "NEWS_CONFIG"
DATA_DIR_ENVIRONMENT_VARIABLE = "NEWS_DATA_DIR"
CONFIG_FILENAME = "config.toml"
DOTENV_FILENAME = ".env"
CREDENTIALS_FILENAME = ".ui_credentials.json"
SESSION_STATE_FILENAME = ".ui_sessions.json"
LOGIN_STATE_FILENAME = ".login_state.json"


def data_dir() -> Path:
    """Return the directory holding operator-owned runtime files.

    Returns
    -------
    Path
        ``NEWS_DATA_DIR`` when that variable is set and non-blank, otherwise
        the process working directory. The directory need not exist yet.
    """
    configured_directory = os.getenv(DATA_DIR_ENVIRONMENT_VARIABLE, "").strip()
    if configured_directory:
        return Path(configured_directory).expanduser().resolve()
    return Path.cwd()


def env_path() -> Path:
    """Return the optional dotenv path in the data directory.

    Returns
    -------
    Path
        Absolute path to ``.env``. The file need not exist.
    """
    return data_dir() / DOTENV_FILENAME


def credentials_path() -> Path:
    """Return the path of the account name and hashed password file."""
    return data_dir() / CREDENTIALS_FILENAME


def session_state_path() -> Path:
    """Return the path of the remembered-session file."""
    return data_dir() / SESSION_STATE_FILENAME


def login_state_path() -> Path:
    """Return the path of the failed-login counter file."""
    return data_dir() / LOGIN_STATE_FILENAME


def config_path(explicit_path: Path | str | None = None) -> Path | None:
    """Find the optional external settings file.

    Resolution order is an explicit caller path, the ``NEWS_CONFIG``
    environment variable, then ``config.toml`` in the current working
    directory. ``None`` means the packaged defaults should be used.

    Parameters
    ----------
    explicit_path : Path | str | None, optional
        Settings path supplied by a command-line or application caller.

    Returns
    -------
    Path | None
        Absolute external settings path, or ``None`` when no external
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
    """Return the installed browser-asset directory.

    Returns
    -------
    Path
        Filesystem path to the package-owned HTML, CSS, and JavaScript assets.
    """
    static_resource = resources.files("news.web").joinpath("static")
    return Path(str(static_resource))
