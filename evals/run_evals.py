"""Run the eval suite: ask the agent each question and grade it against a reference query.

Usage:
    python evals/run_evals.py                  # all cases
    python evals/run_evals.py --only aov       # one case
    python evals/run_evals.py --references     # only run the reference queries (no agent, no API cost)

Writes evals/results.md (scorecard) and evals/results.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from cases import CASES  # noqa: E402

from ask_my_data.agent import ask  # noqa: E402
from ask_my_data.bigquery_client import SafeBigQuery  # noqa: E402
from ask_my_data.config import Settings  # noqa: E402
from ask_my_data.grading import grade  # noqa: E402


def reference_value(bq: SafeBigQuery, case: dict) -> float | None:
    if "reference_sql" not in case:
        return None
    result = bq.run(case["reference_sql"])
    return float(result.rows[0]["value"])


async def run(cases: list[dict], references_only: bool) -> int:
    settings = Settings.from_env()
    bq = SafeBigQuery(settings)
    records = []

    for case in cases:
        expected = reference_value(bq, case)
        print(f"[{case['id']}] reference = {expected}")
        if references_only:
            continue

        started = time.time()
        answer = await ask(case["question"], settings)
        g = grade(case, answer.text, answer.queries, expected)
        status = "PASS" if g.passed else "FAIL"
        print(f"  {status} in {time.time() - started:.0f}s" + ("" if g.passed else f": {'; '.join(g.reasons)}"))
        records.append(
            {
                "id": case["id"],
                "question": case["question"],
                "trap": case.get("trap", ""),
                "passed": g.passed,
                "reasons": g.reasons,
                "expected": expected,
                "found": g.found,
                "queries_run": len(answer.queries),
                "cost_usd": answer.cost_usd,
                "answer": answer.text,
            }
        )

    if references_only:
        return 0

    passed = sum(r["passed"] for r in records)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (HERE / "results.json").write_text(json.dumps(records, indent=2, default=str))

    lines = [
        "# Eval results",
        "",
        f"Run: {stamp} · Score: **{passed}/{len(records)}**",
        "",
        "| Case | Trap tested | Expected | Agent | Result |",
        "|---|---|---|---|---|",
    ]
    for r in records:
        exp = "refusal" if r["expected"] is None else f"{r['expected']:,.2f}"
        got = "—" if r["found"] is None else f"{r['found']:,.2f}"
        res = "✅" if r["passed"] else "❌ " + "; ".join(r["reasons"])
        lines.append(f"| `{r['id']}` | {r['trap']} | {exp} | {got} | {res} |")
    (HERE / "results.md").write_text("\n".join(lines) + "\n")

    print(f"\nScore: {passed}/{len(records)}  ->  evals/results.md")
    return 0 if passed == len(records) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="Case ids to run")
    parser.add_argument("--references", action="store_true", help="Only compute reference values")
    args = parser.parse_args()
    cases = [c for c in CASES if not args.only or c["id"] in args.only]
    return asyncio.run(run(cases, args.references))


if __name__ == "__main__":
    sys.exit(main())
