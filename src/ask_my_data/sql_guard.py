"""Static read-only checks for SQL the agent wants to run.

This is the first of two safety layers. The second layer lives in
``bigquery_client.py``: a BigQuery dry run must report ``statement_type ==
"SELECT"``, every referenced table must belong to an allowed dataset, and the
job runs with a hard ``maximum_bytes_billed`` cap.

The static check is deliberately conservative: it rejects anything it is not
sure is a single read-only query.
"""

from __future__ import annotations

import re

FORBIDDEN_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "TRUNCATE",
    "CREATE",
    "DROP",
    "ALTER",  # REPLACE is not listed: REPLACE() is a string function; CREATE OR REPLACE is caught by CREATE
    "GRANT",
    "REVOKE",
    "EXPORT",
    "LOAD",
    "CALL",
    "EXECUTE",
    "DECLARE",
    "SET",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
)

_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_LINE_COMMENT_RE = re.compile(r"(--|#)[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Single-, double- and backtick-quoted strings/identifiers, with escapes.
_QUOTED_RE = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`[^`]*`")


class UnsafeQueryError(ValueError):
    """Raised when a query is not a single read-only SELECT."""


def _strip_noise(sql: str) -> str:
    """Remove quoted text first (so '--' inside a string survives), then comments."""
    without_quotes = _QUOTED_RE.sub(" '' ", sql)
    without_blocks = _BLOCK_COMMENT_RE.sub(" ", without_quotes)
    return _LINE_COMMENT_RE.sub(" ", without_blocks)


def check_read_only(sql: str) -> str:
    """Return the cleaned query if it looks like one read-only SELECT, else raise.

    Rules:
    * not empty
    * exactly one statement (a single trailing semicolon is allowed)
    * starts with SELECT or WITH
    * no data-changing or scripting keywords outside quoted text
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("Empty query.")

    query = sql.strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()

    scrubbed = _strip_noise(query)

    if ";" in scrubbed:
        raise UnsafeQueryError("Only one statement is allowed per query.")

    first = re.match(r"[\s(]*([A-Za-z_]+)", scrubbed)
    first_word = first.group(1).upper() if first else ""
    if first_word not in {"SELECT", "WITH"}:
        raise UnsafeQueryError(f"Query must start with SELECT or WITH, not {first_word or 'nothing'}.")

    match = _FORBIDDEN_RE.search(scrubbed)
    if match:
        raise UnsafeQueryError(f"Keyword '{match.group(1).upper()}' is not allowed in a read-only query.")

    return query
