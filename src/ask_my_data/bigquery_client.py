"""Thin, safety-first wrapper around the BigQuery client.

Every query goes through three gates before it is billed:

1. ``sql_guard.check_read_only`` - static check for a single SELECT.
2. A BigQuery **dry run** - must report ``statement_type == "SELECT"``, must
   only reference tables in ``allowed_datasets``, and must scan no more than
   ``max_bytes`` (so a runaway query is refused before it costs anything).
3. The real job runs with ``maximum_bytes_billed`` set, so BigQuery itself
   refuses anything larger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from google.cloud import bigquery

from .config import Settings
from .sql_guard import UnsafeQueryError, check_read_only


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    bytes_processed: int
    truncated: bool = False
    sql: str = ""
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "columns": self.columns,
                "rows": self.rows,
                "total_rows": self.total_rows,
                "rows_returned": len(self.rows),
                "truncated": self.truncated,
                "bytes_processed": self.bytes_processed,
                "notes": self.notes,
            },
            default=_json_default,
        )


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


class SafeBigQuery:
    def __init__(self, settings: Settings, client: bigquery.Client | None = None):
        self.settings = settings
        self.client = client or bigquery.Client(project=settings.billing_project)

    # ---------- gates ----------
    def dry_run(self, sql: str) -> bigquery.QueryJob:
        config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self.client.query(sql, job_config=config)

        if (job.statement_type or "").upper() != "SELECT":
            raise UnsafeQueryError(f"Dry run reports statement type {job.statement_type!r}; only SELECT is allowed.")

        for table in job.referenced_tables or []:
            dataset = f"{table.project}.{table.dataset_id}"
            if dataset not in self.settings.allowed_datasets:
                raise UnsafeQueryError(f"Table {dataset}.{table.table_id} is outside the allowed datasets.")

        scanned = job.total_bytes_processed or 0
        if scanned > self.settings.max_bytes:
            raise UnsafeQueryError(
                f"Query would scan {scanned:,} bytes, above the {self.settings.max_bytes:,}-byte limit. "
                "Aggregate more or select fewer columns."
            )
        return job

    # ---------- public API ----------
    def run(self, sql: str) -> QueryResult:
        query = check_read_only(sql)
        self.dry_run(query)

        config = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.settings.max_bytes,
            labels={"app": "ask-my-data"},
        )
        job = self.client.query(query, job_config=config)
        result = job.result(timeout=self.settings.timeout_seconds)

        limit = self.settings.max_rows
        rows: list[dict[str, Any]] = []
        for i, row in enumerate(result):
            if i >= limit:
                break
            rows.append(dict(row.items()))

        total = result.total_rows or len(rows)
        notes = []
        if total > limit:
            notes.append(f"Only the first {limit} of {total} rows were returned. Aggregate further.")

        return QueryResult(
            columns=[f.name for f in result.schema],
            rows=rows,
            total_rows=total,
            bytes_processed=job.total_bytes_processed or 0,
            truncated=total > limit,
            sql=query,
            notes=notes,
        )

    def table_schema(self, table: str) -> dict[str, Any]:
        """Describe one table in an allowed dataset: columns, types, row count."""
        ref = table if "." in table else f"{self.settings.dataset}.{table}"
        dataset = ref.rsplit(".", 1)[0]
        if dataset not in self.settings.allowed_datasets:
            raise UnsafeQueryError(f"{ref} is outside the allowed datasets.")
        t = self.client.get_table(ref)
        return {
            "table": ref,
            "description": t.description,
            "num_rows": t.num_rows,
            "columns": [{"name": f.name, "type": f.field_type, "mode": f.mode} for f in t.schema],
        }
