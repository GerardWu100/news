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

        self.assertIn('"127.0.0.1:50023:8000"', compose)
        self.assertIn("restart: unless-stopped", compose)
        self.assertIn("TZ: America/Toronto", compose)
        # The host folder is an operator setting with the shared default, so
        # the mount must keep both the variable and that fallback.
        self.assertIn(
            "${NEWS_DATA_HOST_DIR:-${HOME}/.containers/news}:/data",
            compose,
        )
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

    def test_image_serves_as_an_unprivileged_account(self) -> None:
        """Root in the container would own every file written to the host."""
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("USER news", dockerfile)
        # The account must be created before it is selected, or the build fails
        # on a machine where the name happens not to exist.
        self.assertLess(
            dockerfile.index("useradd"),
            dockerfile.index("USER news"),
        )

    def test_compose_drops_privileges_and_keeps_the_filesystem_read_only(
        self,
    ) -> None:
        """A compromised process should reach nothing but the mounted data."""
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("cap_drop:", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn('user: "${NEWS_UID:-1000}:${NEWS_GID:-1000}"', compose)

    def test_entrypoint_explains_an_unwritable_data_directory(self) -> None:
        """An unprivileged container cannot fix the mount's owner itself."""
        entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn('if [ ! -w "$DATA_DIR" ]; then', entrypoint)
        self.assertIn("NEWS_UID", entrypoint)

    def test_example_environment_documents_the_container_account(self) -> None:
        """An operator copying the example needs both identifiers present."""
        example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("NEWS_UID=", example)
        self.assertIn("NEWS_GID=", example)
        self.assertIn("NEWS_DATA_HOST_DIR=", example)

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
