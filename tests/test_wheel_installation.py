"""Installed-wheel smoke test for package-owned runtime resources."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class WheelInstallationTests(unittest.TestCase):
    """Verify the built wheel serves the browser outside a source checkout."""

    def test_installed_wheel_serves_index(self) -> None:
        """Build, install, import, and request ``/`` in a clean environment."""
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            distribution_directory = temporary_root / "dist"
            environment_directory = temporary_root / "venv"

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

            smoke_script = (
                "from fastapi.testclient import TestClient\n"
                "from news.api.app import app\n"
                "response = TestClient(app).get('/')\n"
                "assert response.status_code == 200, response.text\n"
                "assert 'News Explorer' in response.text\n"
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
