"""Custom tools the agent can call. They run in-process via the Agent SDK."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from .bigquery_client import SafeBigQuery
from .sql_guard import UnsafeQueryError

SERVER_NAME = "bq"
CHART_DIR = Path("outputs")


def _text(payload: str, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": payload}]}
    if is_error:
        result["is_error"] = True
    return result


def build_server(bq: SafeBigQuery, query_log: list[dict[str, Any]] | None = None):
    """Create the in-process MCP server exposing run_sql, describe_table and make_chart.

    ``query_log`` (optional) collects every SQL attempt and its outcome, which the
    eval harness uses to grade the agent's behaviour, not just its final text.
    Returns ``(server_config, allowed_tool_names)``.
    """
    tools = build_tools(bq, query_log)
    server = create_sdk_mcp_server(name=SERVER_NAME, tools=tools)
    return server, [f"mcp__{SERVER_NAME}__{t.name}" for t in tools]


def build_tools(bq: SafeBigQuery, query_log: list[dict[str, Any]] | None = None):
    """The three tools as SdkMcpTool objects (exposed separately so they can be unit-tested)."""
    log = query_log if query_log is not None else []

    @tool(
        "run_sql",
        "Run ONE read-only BigQuery SELECT against the TheLook dataset and return JSON rows. "
        "Non-SELECT statements, other datasets and very large scans are refused. Aggregate in SQL; "
        "results are capped at a few hundred rows.",
        {"sql": str},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def run_sql(args: dict[str, Any]) -> dict[str, Any]:
        sql = args.get("sql", "")
        try:
            result = bq.run(sql)
        except UnsafeQueryError as exc:
            log.append({"sql": sql, "ok": False, "error": f"refused: {exc}"})
            return _text(f"REFUSED: {exc}", is_error=True)
        except Exception as exc:  # BigQuery syntax errors etc. go back to the model to fix
            log.append({"sql": sql, "ok": False, "error": str(exc)})
            return _text(f"QUERY ERROR: {exc}", is_error=True)
        log.append({"sql": result.sql, "ok": True, "rows": result.total_rows})
        return _text(result.to_json())

    @tool(
        "describe_table",
        "Return columns, types and row count for one table, e.g. 'orders' or 'order_items'.",
        {"table": str},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def describe_table(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _text(json.dumps(bq.table_schema(args.get("table", ""))))
        except Exception as exc:
            return _text(f"ERROR: {exc}", is_error=True)

    @tool(
        "make_chart",
        "Save a simple line or bar chart as a PNG and return its file path.",
        {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["line", "bar"]},
                "title": {"type": "string"},
                "x_labels": {"type": "array", "items": {"type": "string"}},
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["name", "values"],
                    },
                },
                "y_label": {"type": "string"},
            },
            "required": ["kind", "title", "x_labels", "series"],
        },
    )
    async def make_chart(args: dict[str, Any]) -> dict[str, Any]:
        try:
            path = render_chart(**args)
        except Exception as exc:
            return _text(f"ERROR: {exc}", is_error=True)
        return _text(json.dumps({"path": str(path)}))

    return [run_sql, describe_table, make_chart]


def render_chart(
    kind: str,
    title: str,
    x_labels: list[str],
    series: list[dict[str, Any]],
    y_label: str | None = None,
    out_dir: Path = CHART_DIR,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if kind not in {"line", "bar"}:
        raise ValueError("kind must be 'line' or 'bar'")
    for s in series:
        if len(s["values"]) != len(x_labels):
            raise ValueError(f"Series {s['name']!r} has {len(s['values'])} values for {len(x_labels)} labels.")

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "chart"
    path = out_dir / f"{slug}.png"

    fig, ax = plt.subplots(figsize=(9, 4.5))
    n = len(series)
    for i, s in enumerate(series):
        if kind == "line":
            ax.plot(x_labels, s["values"], marker="o", label=s["name"])
        else:
            width = 0.8 / n
            xs = [j + (i - (n - 1) / 2) * width for j in range(len(x_labels))]
            ax.bar(xs, s["values"], width=width, label=s["name"])
    if kind == "bar":
        ax.set_xticks(range(len(x_labels)), x_labels)
    ax.set_title(title)
    if y_label:
        ax.set_ylabel(y_label)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    if n > 1:
        ax.legend(frameon=False)
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
