"""Pure functions that grade an agent answer. Kept separate so they are unit-tested offline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_NUMBER_RE = re.compile(
    r"(?<![\w.])[$]?\s?(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\s?(%|[kKmMbB](?![a-zA-Z]))?"
)
_SCALE = {"k": 1e3, "m": 1e6, "b": 1e9}


def extract_numbers(text: str) -> list[float]:
    """Pull every number out of an answer, understanding commas, %, and K/M/B suffixes.

    "$5.62M" -> 5_620_000, "5,499" -> 5499, "26.4%" -> 26.4, "$85.97" -> 85.97
    """
    values: list[float] = []
    for raw, suffix in _NUMBER_RE.findall(text or ""):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix and suffix.lower() in _SCALE:
            value *= _SCALE[suffix.lower()]
        values.append(value)
    return values


def matches_number(text: str, expected: float, rel_tol: float) -> tuple[bool, float | None]:
    """True if any number in ``text`` is within ``rel_tol`` of ``expected``.

    A small floor on the tolerance lets "$5.62M" match 5,623,417 and "26.4%" match 26.36.
    Returns (matched, closest_value).
    """
    numbers = extract_numbers(text)
    if not numbers:
        return False, None
    closest = min(numbers, key=lambda n: abs(n - expected))
    if expected == 0:
        return closest == 0, closest
    rounding_floor = 0.002 if rel_tol > 0 else 0.0
    tol = max(rel_tol, rounding_floor)
    return abs(closest - expected) / abs(expected) <= tol, closest


@dataclass
class Grade:
    case_id: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    expected: float | None = None
    found: float | None = None


def grade(case: dict[str, Any], answer_text: str, queries: list[dict[str, Any]], expected: float | None) -> Grade:
    reasons: list[str] = []
    found: float | None = None
    text_lower = (answer_text or "").lower()

    if case["check"] == "number":
        ok, found = matches_number(answer_text, expected, case.get("rel_tol", 0.01))
        if not ok:
            reasons.append(f"expected about {expected:,.2f}, closest number in answer was {found}")
    elif case["check"] == "refusal":
        if not any(p in text_lower for p in case["refusal_phrases"]):
            reasons.append("did not say the data can't answer this")
    else:
        reasons.append(f"unknown check type {case['check']!r}")

    for term in case.get("must_mention", []):
        if term.lower() not in text_lower:
            reasons.append(f"answer does not mention {term!r}")

    for pattern in case.get("forbid_sql", []):
        rx = re.compile(pattern, re.IGNORECASE)
        bad = [q for q in queries if q.get("ok") and rx.search(q["sql"])]
        if bad:
            reasons.append(f"ran SQL matching forbidden pattern {pattern!r}")

    if case["check"] == "number" and not any(q.get("ok") for q in queries):
        reasons.append("never ran a successful query")

    return Grade(case_id=case["id"], passed=not reasons, reasons=reasons, expected=expected, found=found)
