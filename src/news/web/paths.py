"""Path helpers for project-level runtime resources.

The package lives under ``src/news`` while runtime resources such as
``config.toml``, ``.env``, and ``frontend/`` live at the project root. This
module centralizes that relationship so API and CLI modules do not duplicate
fragile parent-directory arithmetic.
"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root for a source checkout.

    Returns
    -------
    Path
        Absolute path to the project root directory.
    """
    return Path(__file__).resolve().parents[3]


def env_path() -> Path:
    """Return the project-root dotenv file path."""
    return project_root() / ".env"


def config_path() -> Path:
    """Return the project-root TOML configuration path."""
    return project_root() / "config.toml"


def frontend_dir() -> Path:
    """Return the static frontend asset directory."""
    return project_root() / "frontend"
