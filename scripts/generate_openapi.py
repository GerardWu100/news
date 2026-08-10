"""Generate the checked-in OpenAPI definition from the application routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from news.api.app import create_configured_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "docs" / "reference" / "openapi.json"


def build_parser() -> argparse.ArgumentParser:
    """Build command arguments for OpenAPI generation."""
    parser = argparse.ArgumentParser(
        description="Generate the news API OpenAPI definition.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="JSON output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Generate a stable, human-readable OpenAPI JSON file.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command arguments. ``None`` reads the process arguments.

    Returns
    -------
    int
        Zero after the definition is written successfully.
    """
    args = build_parser().parse_args(argv)
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema = create_configured_app().openapi()
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote OpenAPI definition to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
