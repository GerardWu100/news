"""Installed-wheel smoke test for package-owned runtime resources."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_NAME = "wheel-smoke"
ACCOUNT_PASSWORD = "wheel-smoke-password"


class WheelInstallationTests(unittest.TestCase):
    """Verify the built wheel serves the browser outside a source checkout."""

    def test_installed_wheel_serves_index(self) -> None:
        """Serve the page and favicon from a wheel installed outside the repository."""
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            distribution_directory = temporary_root / "dist"
            environment_directory = temporary_root / "venv"

            # Build and install in isolation so a passing test cannot rely on source files.
            subprocess.run(
                [
                    "uv",
                    "build",
                    "--wheel",
                    "--out-dir",
                    str(distribution_directory),
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "uv",
                    "venv",
                    "--python",
                    sys.executable,
                    str(environment_directory),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            python_executable = environment_directory / "bin" / "python"
            wheel_path = next(distribution_directory.glob("news-*.whl"))
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python_executable),
                    str(wheel_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            # Exercise the packaged resources through one application and
            # client instance. The account comes from the environment, which
            # is what a container passes in, and the credential file lands in
            # the working directory used below.
            smoke_script = (
                "from fastapi.testclient import TestClient\n"
                "from news.api.app import create_configured_app\n"
                "app = create_configured_app()\n"
                "client = TestClient(app)\n"
                "signed_out = client.get('/', follow_redirects=False)\n"
                "assert signed_out.status_code == 302, signed_out.text\n"
                "assert signed_out.headers['location'] == '/login'\n"
                f"response = client.get('/', auth=('{ACCOUNT_NAME}', '{ACCOUNT_PASSWORD}'))\n"
                "assert response.status_code == 200, response.text\n"
                "assert 'Historical News' in response.text\n"
                "favicon = client.get('/static/favicon.svg')\n"
                "assert favicon.status_code == 200, favicon.text\n"
                "assert favicon.headers['content-type'].startswith('image/svg+xml')\n"
            )
            subprocess.run(
                [str(python_executable), "-c", smoke_script],
                cwd=temporary_root,
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "UI_USERNAME": ACCOUNT_NAME,
                    "UI_PASSWORD": ACCOUNT_PASSWORD,
                },
            )
