"""Settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_DATASET = "bigquery-public-data.thelook_ecommerce"


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    billing_project: str
    dataset: str = DEFAULT_DATASET
    allowed_datasets: frozenset[str] = field(default_factory=lambda: frozenset({DEFAULT_DATASET}))
    max_bytes: int = 1_000_000_000  # 1 GB per query; this dataset's tables are far smaller
    max_rows: int = 500
    timeout_seconds: int = 120
    model: str | None = None
    max_turns: int = 20

    @classmethod
    def from_env(cls) -> Settings:
        project = os.getenv("GCP_BILLING_PROJECT")
        if not project:
            raise SystemExit(
                "Set GCP_BILLING_PROJECT to the Google Cloud project that pays for queries "
                "(a free BigQuery sandbox project works). See README > Setup."
            )
        dataset = os.getenv("ASK_MY_DATA_DATASET", DEFAULT_DATASET)
        return cls(
            billing_project=project,
            dataset=dataset,
            allowed_datasets=frozenset({dataset}),
            max_bytes=_int_env("ASK_MY_DATA_MAX_BYTES", 1_000_000_000),
            max_rows=_int_env("ASK_MY_DATA_MAX_ROWS", 500),
            model=os.getenv("ASK_MY_DATA_MODEL") or None,
            max_turns=_int_env("ASK_MY_DATA_MAX_TURNS", 20),
        )
