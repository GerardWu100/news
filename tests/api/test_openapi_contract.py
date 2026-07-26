"""Contract test for the checked-in OpenAPI schema."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from news.api.app import create_configured_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_CONTRACT_PATH = PROJECT_ROOT / "docs" / "reference" / "openapi.json"


class OpenApiContractTests(unittest.TestCase):
    """Require intentional review when public routes or schemas change."""

    def test_generated_openapi_matches_checked_in_contract(self) -> None:
        """Generated routes and models should equal the committed schema."""
        committed_schema = json.loads(
            OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        generated_schema = create_configured_app().openapi()

        self.assertEqual(
            generated_schema,
            committed_schema,
            "OpenAPI changed. Review the API reference and run "
            "`uv run python scripts/generate_openapi.py` if intentional.",
        )


if __name__ == "__main__":
    unittest.main()
