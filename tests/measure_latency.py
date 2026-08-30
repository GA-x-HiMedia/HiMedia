"""Measures Arabic and English agent response latency.

Run:
    python -m tests.measure_latency
    python -m tests.measure_latency --report
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from agent import audit, identity


KHALID = "+97333000003"  # Internal test user.


# Similar Arabic and English requests for comparison.
PAIRS = [
    ("شنو التاسكات اللي عندي اليوم؟", "What are the tasks I have today?"),
    ("وش ينتظر مراجعتي حاليا؟", "What is waiting for my review now?"),
    ("عطني حالة المشاريع الشغالة", "Give me the status of active projects"),
    ("شنو آخر الملاحظات على النسخة؟", "What are the latest notes on the version?"),
    ("وش المهام اللي متأخرة عندي؟", "Which of my tasks are overdue?"),
]


def _run() -> None:
    """Sends the test messages to the agent."""
    from agent import brain

    person = identity.who_is(KHALID)

    if person is None:
        raise SystemExit(
            f"{KHALID} did not resolve — is the sandbox reachable?"
        )

    phone = identity.tidy(KHALID)

    for arabic, english in PAIRS:
        for message in (arabic, english):
            print(f"  asking: {message}")

            try:
                brain.reply_to(person, message, phone)

            except Exception as broke:
                print(
                    f"    FAILED: {type(broke).__name__}: {broke}"
                )


def _stages() -> list[dict]:
    """Reads stage timing records from the audit log."""
    path = Path(audit.AUDIT_LOG_PATH)

    if not path.exists():
        return []

    rows = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():

        try:
            event = json.loads(line)

        except ValueError:
            continue

        if "stage" in event:
            rows.append(event)

    return rows


def _mean(values: list[float]) -> str:
    """Returns the mean value or a placeholder."""
    return (
        f"{sum(values) / len(values):.0f}"
        if values
        else "-"
    )


def report() -> str:
    """Creates a latency report for Arabic and English requests."""
    rows = _stages()

    if not rows:
        return (
            "No stage records in audit.log.\n"
            "Run `python -m tests.measure_latency` against a reachable sandbox "
            "first — an empty table is not a fast one."
        )

    per_stage: dict[
        str,
        dict[str, list[float]]
    ] = defaultdict(
        lambda: {"ar": [], "en": []}
    )

    rounds: dict[str, list[int]] = {
        "ar": [],
        "en": [],
    }

    cache = {
        "cache hit": 0,
        "live fetch": 0,
        "unknown number": 0,
    }

    for event in rows:
        stage = event["stage"]
        detail = event.get("detail") or ""

        if stage == "identity.who_is":
            cache[detail] = cache.get(detail, 0) + 1
            language = None

        else:
            language = (
                "ar"
                if "ar" in detail.split() or detail == "ar"
                else (
                    "en"
                    if "en" in detail.split() or detail == "en"
                    else None
                )
            )

        if stage == "rounds_used":
            used = int(detail.split()[0])

            if language:
                rounds[language].append(used)

            continue

        if stage == "identity.who_is":
            # Identity lookup is not language-specific.
            per_stage[stage]["ar"].append(
                event["duration_ms"]
            )
            continue

        if language:
            per_stage[stage][language].append(
                event["duration_ms"]
            )

    lines = []

    lines.append(
        f"{'stage':<24} "
        f"{'mean ms AR':>12} "
        f"{'mean ms EN':>12}   "
        f"{'n AR':>5} "
        f"{'n EN':>5}"
    )

    lines.append("-" * 66)

    for stage in sorted(
        per_stage,
        key=lambda s: (s != "identity.who_is", s),
    ):
        ar = per_stage[stage]["ar"]
        en = per_stage[stage]["en"]

        if stage == "identity.who_is":
            lines.append(
                f"{stage:<24} "
                f"{_mean(ar):>12} "
                f"{'(same)':>12}   "
                f"{len(ar):>5} "
                f"{'-':>5}"
            )

        else:
            lines.append(
                f"{stage:<24} "
                f"{_mean(ar):>12} "
                f"{_mean(en):>12}   "
                f"{len(ar):>5} "
                f"{len(en):>5}"
            )

    lines.append("")

    for language in ("ar", "en"):
        used = rounds[language]

        if used:
            lines.append(
                f"rounds used ({language}): "
                f"mean {sum(used) / len(used):.1f}, "
                f"max {max(used)} of 6 — "
                f"messages measured: {len(used)}"
            )

    lines.append("")

    lines.append(
        f"identity.who_is: "
        f"{cache.get('cache hit', 0)} cache hits, "
        f"{cache.get('live fetch', 0)} live fetches "
        f"(CACHE_SECONDS = {identity.CACHE_SECONDS})"
    )

    return "\n".join(lines)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )

    if "--report" not in sys.argv:
        _run()

    print()
    print(report())