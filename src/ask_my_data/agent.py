"""Wire the tools and the analyst prompt into a Claude Agent SDK agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from .bigquery_client import SafeBigQuery
from .config import Settings
from .tools import build_server


def load_system_prompt() -> str:
    return resources.files("ask_my_data.prompts").joinpath("system.md").read_text(encoding="utf-8")


def build_options(
    settings: Settings, bq: SafeBigQuery, query_log: list[dict[str, Any]] | None = None
) -> ClaudeAgentOptions:
    server, tool_names = build_server(bq, query_log)
    return ClaudeAgentOptions(
        system_prompt=load_system_prompt(),
        mcp_servers={"bq": server},
        tools=[],  # no built-in tools: no shell, no file edits, no web
        allowed_tools=tool_names,  # our three tools run without permission prompts
        setting_sources=[],  # ignore any local Claude Code settings / CLAUDE.md
        max_turns=settings.max_turns,
        model=settings.model,
    )


@dataclass
class AgentAnswer:
    text: str
    queries: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float | None = None
    turns: int | None = None
    is_error: bool = False


async def ask(question: str, settings: Settings | None = None, verbose: bool = False) -> AgentAnswer:
    """Ask the agent one question and return its final answer plus the SQL it ran."""
    settings = settings or Settings.from_env()
    bq = SafeBigQuery(settings)
    query_log: list[dict[str, Any]] = []
    options = build_options(settings, bq, query_log)

    final_text = ""
    answer = AgentAnswer(text="", queries=query_log)
    async for message in query(prompt=question, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    final_text = block.text
                elif isinstance(block, ToolUseBlock) and verbose:
                    preview = str(block.input.get("sql", block.input))[:200].replace("\n", " ")
                    print(f"  -> {block.name.split('__')[-1]}: {preview}")
        elif isinstance(message, ResultMessage):
            answer.cost_usd = message.total_cost_usd
            answer.turns = message.num_turns
            answer.is_error = message.is_error
            if message.result:
                final_text = message.result

    answer.text = final_text
    return answer
