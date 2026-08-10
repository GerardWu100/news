"""Load and validate application settings.

Packaged TOML defines each default once. An external TOML file may override a
subset, but unknown tables, misspelled keys, invalid source names, and
non-positive cache limits fail before the application starts.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from news.sources.registry import source_names
from news.web.paths import config_path

ROOT_SETTING_KEYS = frozenset({"frontend", "cache"})
FRONTEND_SETTING_KEYS = frozenset({"default_english_only", "default_sources"})
CACHE_SETTING_KEYS = frozenset({"ttl_seconds", "max_entries"})


class SettingsError(ValueError):
    """Raised when application settings are missing or invalid."""


@dataclass(frozen=True, slots=True)
class FrontendSettings:
    """Browser defaults exposed by the configuration API.

    Attributes
    ----------
    default_english_only : bool
        Whether the initial browser form selects English-only filtering.
    default_sources : tuple[str, ...]
        Ordered source names selected when the browser first loads.
    """

    default_english_only: bool
    default_sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a mapping that can be converted to JSON."""
        return {
            "default_english_only": self.default_english_only,
            "default_sources": list(self.default_sources),
        }


@dataclass(frozen=True, slots=True)
class CacheSettings:
    """In-memory search-cache limits.

    Attributes
    ----------
    ttl_seconds : int
        Number of seconds to keep each cached search result.
    max_entries : int
        Maximum number of current search results kept in one process.
    """

    ttl_seconds: int
    max_entries: int


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Complete application settings."""

    frontend: FrontendSettings
    cache: CacheSettings


def load_settings(path: Path | str | None = None) -> AppSettings:
    """Load packaged defaults, apply an external override, and validate them.

    Parameters
    ----------
    path : Path | str | None, optional
        Explicit configuration path. ``None`` applies standard path resolution.

    Returns
    -------
    AppSettings
        Validated settings for building the application.

    Raises
    ------
    SettingsError
        If the selected file is missing, malformed, or contains invalid values.
    """
    default_config = _read_packaged_defaults()
    external_path = config_path(path)
    if external_path is None:
        merged_config = default_config
    else:
        external_config = _read_toml_path(external_path)
        _validate_known_keys(external_config, source=str(external_path))
        merged_config = _merge_tables(default_config, external_config)
    return _parse_settings(merged_config)


def _read_packaged_defaults() -> dict[str, Any]:
    """Read the package-owned default configuration."""
    default_resource = resources.files("news.web").joinpath("default_config.toml")
    try:
        with default_resource.open("rb") as config_file:
            config = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(
            f"Packaged default configuration is malformed: {exc}"
        ) from exc
    _validate_known_keys(config, source="packaged defaults")
    return config


def _read_toml_path(path: Path) -> dict[str, Any]:
    """Read one external TOML file and report settings errors clearly."""
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise SettingsError(f"Configuration file does not exist: {path}") from exc
    except OSError as exc:
        raise SettingsError(f"Cannot read configuration file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(
            f"Malformed TOML in configuration file {path}: {exc}"
        ) from exc


def _validate_known_keys(config: Mapping[str, Any], *, source: str) -> None:
    """Reject unknown tables and setting names before reading values."""
    _reject_unknown_keys(config, ROOT_SETTING_KEYS, location=source)
    for table_name, allowed_keys in (
        ("frontend", FRONTEND_SETTING_KEYS),
        ("cache", CACHE_SETTING_KEYS),
    ):
        table = config.get(table_name, {})
        if not isinstance(table, Mapping):
            raise SettingsError(f"{table_name} must be a TOML table in {source}")
        _reject_unknown_keys(
            table,
            allowed_keys,
            location=f"{source} [{table_name}]",
        )


def _reject_unknown_keys(
    values: Mapping[str, Any],
    allowed_keys: frozenset[str],
    *,
    location: str,
) -> None:
    """Raise for misspelled or unsupported settings."""
    unknown_keys = sorted(set(values) - allowed_keys)
    if unknown_keys:
        joined_keys = ", ".join(unknown_keys)
        raise SettingsError(
            f"Unknown configuration key(s) in {location}: {joined_keys}"
        )


def _merge_tables(
    defaults: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply external table values to independent copies of the defaults."""
    merged = {
        table_name: dict(table_values) for table_name, table_values in defaults.items()
    }
    for table_name, table_values in overrides.items():
        merged[table_name].update(table_values)
    return merged


def _parse_settings(config: Mapping[str, Any]) -> AppSettings:
    """Convert a validated-key mapping into typed settings."""
    frontend = config["frontend"]
    cache = config["cache"]

    default_english_only = frontend["default_english_only"]
    if not isinstance(default_english_only, bool):
        raise SettingsError("frontend.default_english_only must be true or false")

    raw_sources = frontend["default_sources"]
    if not isinstance(raw_sources, list) or not all(
        isinstance(source, str) for source in raw_sources
    ):
        raise SettingsError("frontend.default_sources must be an array of source names")

    # Clean names once, then compare them with the registry used for source
    # selection so settings and runtime use the same names.
    normalized_sources = tuple(source.strip().lower() for source in raw_sources)
    known_sources = source_names()
    invalid_sources = sorted(set(normalized_sources) - known_sources)
    if invalid_sources:
        allowed = ", ".join(sorted(known_sources))
        invalid = ", ".join(invalid_sources)
        raise SettingsError(
            f"Unknown frontend.default_sources value(s): {invalid}. "
            f"Allowed values: {allowed}"
        )
    if any(not source for source in normalized_sources):
        raise SettingsError("frontend.default_sources cannot contain blank names")
    if len(set(normalized_sources)) != len(normalized_sources):
        raise SettingsError("frontend.default_sources cannot contain duplicates")

    return AppSettings(
        frontend=FrontendSettings(
            default_english_only=default_english_only,
            default_sources=normalized_sources,
        ),
        cache=CacheSettings(
            ttl_seconds=_positive_integer(cache["ttl_seconds"], "cache.ttl_seconds"),
            max_entries=_positive_integer(
                cache["max_entries"],
                "cache.max_entries",
            ),
        ),
    )


def _positive_integer(value: object, field_name: str) -> int:
    """Validate a positive integer setting without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SettingsError(f"{field_name} must be a positive integer")
    return value
