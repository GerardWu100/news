"""Write normalized search results in export formats.

The backend exposes CSV and JSON downloads through HTTP routes. The CLI can
also append results to SQLite. All writers use the common article dictionaries
created by the search process.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from datetime import UTC, datetime
from typing import Any

_CSV_COLUMNS = [
    "title",
    "url",
    "date",
    "source",
    "domain",
    "language",
    "summary",
    "section",
    "author",
    "matched_sources",
    "duplicate_count",
]

_CSV_COLUMNS_WITH_CONTENT = [
    "title",
    "url",
    "date",
    "source",
    "domain",
    "language",
    "summary",
    "content",
    "section",
    "author",
    "matched_sources",
    "duplicate_count",
]

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    date TEXT NOT NULL,
    source TEXT NOT NULL,
    domain TEXT DEFAULT '',
    language TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    content TEXT DEFAULT '',
    section TEXT DEFAULT '',
    author TEXT DEFAULT '',
    matched_sources TEXT DEFAULT '',
    duplicate_count INTEGER DEFAULT 1,
    query TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(url, query)
);
"""

_SQLITE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);",
    "CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);",
    "CREATE INDEX IF NOT EXISTS idx_articles_query ON articles(query);",
]

_SQLITE_INSERT_ARTICLE = """
INSERT OR IGNORE INTO articles (
    title,
    url,
    date,
    source,
    domain,
    language,
    summary,
    content,
    section,
    author,
    matched_sources,
    duplicate_count,
    query,
    fetched_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def format_csv(
    articles: list[dict[str, Any]],
    *,
    include_content: bool = False,
) -> str:
    """Convert normalized article rows to CSV text."""
    columns = _CSV_COLUMNS_WITH_CONTENT if include_content else _CSV_COLUMNS
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()

    for article in articles:
        row = dict(article)
        row["matched_sources"] = _serialize_matched_sources(
            row.get("matched_sources", [])
        )
        writer.writerow(row)

    return output.getvalue()


def format_json(articles: list[dict[str, Any]]) -> str:
    """Convert normalized article rows to readable JSON."""
    return json.dumps(articles, indent=2, ensure_ascii=False)


def write_sqlite(
    articles: list[dict[str, Any]],
    db_path: str,
    query: str,
) -> int:
    """Append normalized article rows to a SQLite database.

    Parameters
    ----------
    articles : list[dict[str, Any]]
        Normalized article dictionaries from the search process.
    db_path : str
        Destination SQLite database path.
    query : str
        Search query stored with each row for later reference.

    Returns
    -------
    int
        Number of new rows inserted. Existing ``(url, query)`` pairs are
        ignored by the table's uniqueness constraint.
    """
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute(_SQLITE_SCHEMA)
        for index_sql in _SQLITE_INDEXES:
            connection.execute(index_sql)

        fetched_at = datetime.now(UTC).isoformat()
        inserted = 0

        for article in articles:
            # Keep the SQL statement and row values separate so the table
            # columns are easy to compare with the values written.
            cursor = connection.execute(
                _SQLITE_INSERT_ARTICLE,
                _sqlite_article_values(article, query=query, fetched_at=fetched_at),
            )
            inserted += cursor.rowcount

        return inserted


def _sqlite_article_values(
    article: dict[str, Any],
    *,
    query: str,
    fetched_at: str,
) -> tuple[object, ...]:
    """Build the SQLite row tuple for one normalized article.

    The ordering mirrors ``_SQLITE_INSERT_ARTICLE`` exactly. Missing optional
    fields default to empty strings so sparse provider records still export
    through the same schema.
    """
    return (
        article.get("title", ""),
        article.get("url", ""),
        article.get("date", ""),
        article.get("source", ""),
        article.get("domain", ""),
        article.get("language", ""),
        article.get("summary", ""),
        article.get("content", ""),
        article.get("section", ""),
        article.get("author", ""),
        _serialize_matched_sources(article.get("matched_sources", [])),
        article.get("duplicate_count", 1),
        query,
        fetched_at,
    )


def _serialize_matched_sources(value: object) -> str:
    """Convert source lists into a stable JSON string."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return json.dumps(list(value))
    return str(value)
