"""Installed-wheel smoke test for package-owned runtime resources."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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

            # Exercise both packaged resources through one application and client instance.
            smoke_script = (
                "from fastapi.testclient import TestClient\n"
                "from news.api.app import create_configured_app\n"
                "app = create_configured_app()\n"
                "client = TestClient(app)\n"
                "response = client.get('/')\n"
                "assert response.status_code == 200, response.text\n"
                "assert 'Point-in-Time News' in response.text\n"
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
            )


if __name__ == "__main__":
    unittest.main()
