"""Offline tests for the BigQuery wrapper and tools, using a fake BigQuery client."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from ask_my_data.bigquery_client import SafeBigQuery
from ask_my_data.config import Settings
from ask_my_data.sql_guard import UnsafeQueryError
from ask_my_data.tools import build_server, build_tools, render_chart

DATASET = "bigquery-public-data.thelook_ecommerce"


class FakeRow(dict):
    """BigQuery Row stand-in: supports .items() like the real thing."""


class FakeResult(list):
    def __init__(self, rows):
        super().__init__(rows)
        self.schema = [SimpleNamespace(name=k) for k in rows[0]]
        self.total_rows = len(rows)


class FakeJob:
    def __init__(self, statement_type="SELECT", datasets=(DATASET,), scanned=1_000, rows=None):
        self.statement_type = statement_type
        self.referenced_tables = [
            SimpleNamespace(project=d.split(".")[0], dataset_id=d.split(".")[1], table_id="t") for d in datasets
        ]
        self.total_bytes_processed = scanned
        self._rows = rows or [FakeRow(value=42)]

    def result(self, timeout=None):
        return FakeResult(self._rows)


class FakeClient:
    def __init__(self, job):
        self.job = job
        self.calls = []

    def query(self, sql, job_config=None):
        self.calls.append((sql, job_config))
        return self.job


def make(job):
    settings = Settings(billing_project="test-project", max_bytes=10_000)
    client = FakeClient(job)
    return SafeBigQuery(settings, client=client), client


def test_runs_select_with_cost_cap():
    bq, client = make(FakeJob())
    result = bq.run("SELECT 42 AS value")
    assert result.rows == [{"value": 42}]
    (_, dry_cfg), (_, real_cfg) = client.calls
    assert dry_cfg.dry_run is True
    assert real_cfg.maximum_bytes_billed == 10_000


def test_static_guard_runs_before_bigquery():
    bq, client = make(FakeJob())
    with pytest.raises(UnsafeQueryError):
        bq.run("DROP TABLE x")
    assert client.calls == []  # nothing reached BigQuery


def test_dry_run_rejects_non_select():
    bq, _ = make(FakeJob(statement_type="DELETE"))
    with pytest.raises(UnsafeQueryError, match="statement type"):
        bq.run("SELECT 1")


def test_dry_run_rejects_other_datasets():
    bq, _ = make(FakeJob(datasets=("my-company.payroll",)))
    with pytest.raises(UnsafeQueryError, match="outside the allowed datasets"):
        bq.run("SELECT 1")


def test_dry_run_rejects_huge_scans():
    bq, client = make(FakeJob(scanned=10_000_000))
    with pytest.raises(UnsafeQueryError, match="limit"):
        bq.run("SELECT 1")
    assert len(client.calls) == 1  # only the free dry run happened


def test_rows_are_capped():
    bq, _ = make(FakeJob(rows=[FakeRow(value=i) for i in range(600)]))
    result = bq.run("SELECT 1")
    assert len(result.rows) == 500 and result.truncated
    assert json.loads(result.to_json())["truncated"] is True


def test_server_exposes_three_tools():
    bq, _ = make(FakeJob())
    server, names = build_server(bq)
    assert names == ["mcp__bq__run_sql", "mcp__bq__describe_table", "mcp__bq__make_chart"]
    assert server["name"] == "bq"


def test_run_sql_tool_returns_rows_and_logs():
    bq, _ = make(FakeJob())
    log = []
    run_sql = next(t for t in build_tools(bq, log) if t.name == "run_sql")
    out = asyncio.run(run_sql.handler({"sql": "SELECT 42 AS value"}))
    assert not out.get("is_error")
    assert json.loads(out["content"][0]["text"])["rows"] == [{"value": 42}]
    assert log == [{"sql": "SELECT 42 AS value", "ok": True, "rows": 1}]


def test_run_sql_tool_reports_refusal_to_the_model():
    bq, _ = make(FakeJob())
    log = []
    run_sql = next(t for t in build_tools(bq, log) if t.name == "run_sql")
    out = asyncio.run(run_sql.handler({"sql": "DELETE FROM orders"}))
    assert out["is_error"] and out["content"][0]["text"].startswith("REFUSED")
    assert log[0]["ok"] is False


def test_render_chart(tmp_path):
    path = render_chart(
        kind="bar",
        title="Top categories",
        x_labels=["A", "B"],
        series=[{"name": "Revenue", "values": [1, 2]}],
        out_dir=tmp_path,
    )
    assert path.exists() and path.suffix == ".png"


def test_render_chart_rejects_mismatched_lengths(tmp_path):
    with pytest.raises(ValueError):
        render_chart(kind="line", title="x", x_labels=["A"], series=[{"name": "s", "values": [1, 2]}], out_dir=tmp_path)
