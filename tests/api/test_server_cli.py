"""Subprocess tests for server startup and configuration precedence."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class ServerCommandTests(unittest.TestCase):
    """Verify command parsing occurs before application configuration."""

    def test_explicit_config_overrides_malformed_working_directory_config(
        self,
    ) -> None:
        """A valid ``--config`` must bypass an invalid local ``config.toml``."""
        with TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            (temporary_path / "config.toml").write_text(
                "[cache\n",
                encoding="utf-8",
            )
            explicit_config = temporary_path / "valid.toml"
            explicit_config.write_text(
                "[cache]\nttl_seconds = 60\n",
                encoding="utf-8",
            )

            startup_script = (
                "import os\n"
                "import sys\n"
                "import types\n"
                "def fake_run(target, **kwargs):\n"
                "    assert target == 'news.api.app:create_configured_app'\n"
                "    assert kwargs['factory'] is True\n"
                "    from news.api.app import create_configured_app\n"
                "    app = create_configured_app()\n"
                "    assert app.state.settings.cache.ttl_seconds == 60\n"
                "sys.modules['uvicorn'] = types.SimpleNamespace(run=fake_run)\n"
                "from news.api.app import main\n"
                f"main(['--config', {str(explicit_config)!r}])\n"
                "assert os.environ['NEWS_CONFIG'] == "
                f"{str(explicit_config)!r}\n"
            )
            subprocess.run(
                [sys.executable, "-c", startup_script],
                cwd=temporary_path,
                check=True,
                capture_output=True,
                text=True,
            )
