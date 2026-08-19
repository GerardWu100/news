"""Static tests for the self-hosted Docker deployment files."""

from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DockerDeploymentTests(unittest.TestCase):
    """Protect the deployment defaults shared with the reference project."""

    def test_compose_keeps_server_private_and_persistent(self) -> None:
        """Compose should bind loopback and mount operator-owned configuration."""
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn('"127.0.0.1:50024:8000"', compose)
        self.assertIn("restart: unless-stopped", compose)
        self.assertIn("TZ: America/Toronto", compose)
        self.assertIn("${HOME}/.containers/news:/data", compose)
        self.assertIn("NEWS_CONFIG: /data/config.toml", compose)
        self.assertIn("NEWS_SERVER_URL: http://news:8000", compose)
        self.assertIn("external: true", compose)

    def test_compose_passes_the_account_and_checks_an_open_route(self) -> None:
        """The container needs the account, and its health check must not need one."""
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("UI_USERNAME: ${UI_USERNAME:-}", compose)
        self.assertIn("UI_PASSWORD: ${UI_PASSWORD:-}", compose)
        self.assertIn("/healthz", compose)
        self.assertNotIn("/api/config', timeout=5", compose)

    def test_image_runs_server_on_all_container_interfaces(self) -> None:
        """The image command should make the server reachable through Docker."""
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("python:3.13-slim", dockerfile)
        self.assertIn("ghcr.io/astral-sh/uv", dockerfile)
        self.assertIn(
            'CMD ["news-server", "--host", "0.0.0.0", "--port", "8000"]',
            dockerfile,
        )

    def test_image_creates_no_account(self) -> None:
        """The image matches the reference project: no account is created.

        Debian's base image already defines a system user and group named
        "news", so a `groupadd news` here would fail the build outright.
        """
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertNotIn("useradd", dockerfile)
        self.assertNotIn("groupadd", dockerfile)
        self.assertNotIn("USER ", dockerfile)

    def test_compose_pins_no_account_and_keeps_the_filesystem_read_only(
        self,
    ) -> None:
        """A compromised process should reach nothing but the mounted data."""
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("read_only: true", compose)
        self.assertNotIn("user:", compose)

    def test_entrypoint_creates_the_data_directory(self) -> None:
        """The container owns the mount, so it makes the directory itself."""
        entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn('mkdir -p "$DATA_DIR"', entrypoint)
        self.assertIn('mkdir -p "$(dirname "$CONFIG_PATH")"', entrypoint)

    def test_entrypoint_seeds_config_without_overwriting_operator_changes(self) -> None:
        """First boot should copy defaults only when no mounted config exists."""
        entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn('if [ ! -f "$CONFIG_PATH" ]; then', entrypoint)
        self.assertIn('cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"', entrypoint)

    def test_entrypoint_warns_when_the_account_is_missing(self) -> None:
        """A closed server is easier to diagnose from the container log."""
        entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn('[ -z "${UI_USERNAME:-}" ]', entrypoint)
        self.assertIn('[ -z "${UI_PASSWORD:-}" ]', entrypoint)
