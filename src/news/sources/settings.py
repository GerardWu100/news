"""Deployment settings that every source adapter reads.

Adapters are constructed once and reused, so they cannot take these values as
constructor arguments without rebuilding the registry. The server and the two
command-line entry points instead call :func:`configure_sources` once at
startup, and adapters read the current values when they build a request.

Anything not configured keeps the module defaults below, so importing an
adapter in a test needs no setup.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Seconds allowed to open a connection, including the Transport Layer Security
# (TLS) handshake. Some providers are slow to negotiate TLS from a given host:
# api.gdeltproject.org measured 12.5 seconds from the deployment machine on
# 2026-08-11, so a short limit fails every request before any data is sent.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 25.0

# Seconds allowed between the request being sent and the response arriving.
DEFAULT_READ_TIMEOUT_SECONDS = 20.0

# MediaCloud "collections" are curated groups of outlets. The story-list
# endpoint rejects a search that names no collection and no source, so a
# default is required for the adapter to work at all. 34412234 is MediaCloud's
# own "United States - National" collection, the group its web interface uses
# for a first-time query.
DEFAULT_MEDIACLOUD_COLLECTIONS: tuple[int, ...] = (34412234,)


@dataclass(frozen=True, slots=True)
class SourceSettings:
    """Values that change how adapters talk to their providers.

    Attributes
    ----------
    connect_timeout_seconds : float
        Seconds allowed to open a connection and complete the TLS handshake.
    read_timeout_seconds : float
        Seconds allowed to wait for a response once the request has been sent.
    mediacloud_collections : tuple[int, ...]
        MediaCloud collection identifiers searched together. An empty tuple is
        not useful because the provider requires at least one.
    """

    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    mediacloud_collections: tuple[int, ...] = field(
        default=DEFAULT_MEDIACLOUD_COLLECTIONS
    )


_current_settings = SourceSettings()


def configure_sources(settings: SourceSettings) -> None:
    """Replace the settings every adapter reads from now on.

    Parameters
    ----------
    settings : SourceSettings
        Values parsed from the ``[sources]`` configuration table.
    """
    global _current_settings
    _current_settings = settings


def current_source_settings() -> SourceSettings:
    """Return the settings adapters should use for the next request."""
    return _current_settings
