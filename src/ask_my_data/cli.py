"""Command line: `ask-my-data "What was revenue by month this year?"` or interactive mode."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .agent import ask
from .config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ask-my-data", description="Ask the TheLook store data a question.")
    parser.add_argument("question", nargs="*", help="Your question. Leave empty for interactive mode.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show each tool call as it happens.")
    parser.add_argument("--show-sql", action="store_true", help="Print every SQL attempt after the answer.")
    args = parser.parse_args(argv)

    settings = Settings.from_env()

    def run_once(q: str) -> None:
        answer = asyncio.run(ask(q, settings, verbose=args.verbose))
        print("\n" + answer.text.strip() + "\n")
        if args.show_sql:
            for i, entry in enumerate(answer.queries, 1):
                status = "ok" if entry["ok"] else entry.get("error", "failed")
                print(f"--- query {i} ({status}) ---\n{entry['sql']}\n")
        if answer.cost_usd is not None:
            print(f"[{answer.turns} turns, ${answer.cost_usd:.4f}]")

    if args.question:
        run_once(" ".join(args.question))
        return 0

    print("Ask a question about the TheLook store (blank line to quit).")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        run_once(q)
    return 0


if __name__ == "__main__":
    sys.exit(main())
