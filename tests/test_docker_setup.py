"""Static contract tests for the self-hosted Docker deployment files."""

from __future__ import annotations

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DockerDeploymentTests(unittest.TestCase):
    """Protect the deployment defaults shared with the reference project."""

    def test_compose_keeps_server_private_and_persistent(self) -> None:
        """Compose should bind loopback and mount operator-owned configuration."""
        compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn('"127.0.0.1:50023:8000"', compose)
        self.assertIn("restart: unless-stopped", compose)
        self.assertIn("TZ: America/Toronto", compose)
        self.assertIn("${HOME}/.containers/news:/data", compose)
        self.assertIn("NEWS_CONFIG: /data/config.toml", compose)
        self.assertIn("NEWS_SERVER_URL: http://news:8000", compose)
        self.assertIn("external: true", compose)

    def test_image_runs_server_on_all_container_interfaces(self) -> None:
        """The image command should make the server reachable through Docker."""
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("python:3.13-slim", dockerfile)
        self.assertIn("ghcr.io/astral-sh/uv", dockerfile)
        self.assertIn(
            'CMD ["news-server", "--host", "0.0.0.0", "--port", "8000"]',
            dockerfile,
        )

    def test_entrypoint_seeds_config_without_overwriting_operator_changes(self) -> None:
        """First boot should copy defaults only when no mounted config exists."""
        entrypoint = (PROJECT_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")

        self.assertIn('if [ ! -f "$CONFIG_PATH" ]; then', entrypoint)
        self.assertIn('cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"', entrypoint)
