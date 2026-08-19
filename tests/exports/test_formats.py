"""Regression tests for CSV, JSON, and SQLite export helpers."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from news.exports.formats import format_csv, format_json, write_sqlite

SAMPLE_ARTICLES = [
    {
        "title": "Fed holds rates steady",
        "url": "https://example.com/fed",
        "date": "2026-03-20",
        "source": "guardian",
        "domain": "example.com",
        "language": "en",
        "summary": "Officials left rates unchanged.",
        "content": "Full body text here.",
        "section": "Business",
        "author": "Jane Doe",
        "matched_sources": ["guardian"],
        "duplicate_count": 1,
    },
    {
        "title": "Markets rally on data",
        "url": "https://example.com/markets",
        "date": "2026-03-19",
        "source": "nyt",
        "domain": "nytimes.com",
        "language": "en",
        "summary": "Stocks rose sharply.",
        "content": "",
        "section": "Markets",
        "author": "John Smith",
        "matched_sources": ["nyt", "gdelt"],
        "duplicate_count": 2,
    },
]


class CsvExportTests(unittest.TestCase):
    """Test CSV formatting."""

    def test_format_csv_excludes_content_by_default(self) -> None:
        """CSV output should exclude the large content field by default."""
        output = format_csv(SAMPLE_ARTICLES, include_content=False)
        rows = list(csv.DictReader(io.StringIO(output)))

        self.assertEqual(len(rows), 2)
        self.assertNotIn("content", rows[0])
        self.assertEqual(rows[0]["title"], "Fed holds rates steady")

    def test_format_csv_includes_content_when_requested(self) -> None:
        """CSV output should include content when the caller opts in."""
        output = format_csv(SAMPLE_ARTICLES, include_content=True)
        rows = list(csv.DictReader(io.StringIO(output)))

        self.assertIn("content", rows[0])
        self.assertEqual(rows[0]["content"], "Full body text here.")

    def test_format_csv_serializes_matched_sources_as_json(self) -> None:
        """CSV output should keep source names as a JSON string."""
        output = format_csv(SAMPLE_ARTICLES)
        rows = list(csv.DictReader(io.StringIO(output)))

        self.assertEqual(rows[1]["matched_sources"], '["nyt", "gdelt"]')

    def test_format_csv_neutralizes_spreadsheet_formulas(self) -> None:
        """Provider text must remain inert when a CSV is opened in a spreadsheet."""
        dangerous_article = {**SAMPLE_ARTICLES[0], "title": '=HYPERLINK("x")'}

        rows = list(csv.DictReader(io.StringIO(format_csv([dangerous_article]))))

        self.assertEqual(rows[0]["title"], '\'=HYPERLINK("x")')


class JsonExportTests(unittest.TestCase):
    """Test JSON formatting."""

    def test_format_json_returns_valid_json_array(self) -> None:
        """JSON export should return the raw articles array."""
        output = format_json(SAMPLE_ARTICLES)
        parsed = json.loads(output)

        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["title"], "Fed holds rates steady")


class SqliteExportTests(unittest.TestCase):
    """Test SQLite append behavior."""

    def test_write_sqlite_creates_table_and_inserts_rows(self) -> None:
        """SQLite export should create the target table and insert rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            write_sqlite(SAMPLE_ARTICLES, str(db_path), query="fed")

            connection = sqlite3.connect(str(db_path))
            count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            rows = connection.execute(
                "SELECT title, query FROM articles ORDER BY date DESC"
            ).fetchall()
            connection.close()

        self.assertEqual(count, 2)
        self.assertEqual(rows[0][0], "Fed holds rates steady")
        self.assertEqual(rows[0][1], "fed")

    def test_write_sqlite_ignores_duplicate_url_query_pairs(self) -> None:
        """Re-running the same query should not duplicate identical rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            write_sqlite(SAMPLE_ARTICLES, str(db_path), query="fed")
            write_sqlite(SAMPLE_ARTICLES, str(db_path), query="fed")

            connection = sqlite3.connect(str(db_path))
            count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            connection.close()

        self.assertEqual(count, 2)

    def test_write_sqlite_allows_same_url_with_different_query(self) -> None:
        """The same article may be stored under multiple research queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            write_sqlite(SAMPLE_ARTICLES[:1], str(db_path), query="fed")
            write_sqlite(SAMPLE_ARTICLES[:1], str(db_path), query="rates")

            connection = sqlite3.connect(str(db_path))
            count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            connection.close()

        self.assertEqual(count, 2)

    def test_write_sqlite_closes_connection_without_resource_warning(self) -> None:
        """SQLite export should not leak a connection after writing rows."""
        import gc
        import warnings

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                write_sqlite(SAMPLE_ARTICLES, str(db_path), query="fed")
                gc.collect()

        resource_warnings = [
            warning
            for warning in caught
            if issubclass(warning.category, ResourceWarning)
        ]
        self.assertEqual(resource_warnings, [])
