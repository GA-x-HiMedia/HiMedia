"""
Where the time goes, Arabic vs English. Measurement only — this changes no
behaviour and draws no conclusions about what to do about it.

    python -m tests.measure_latency              # send the messages, then report
    python -m tests.measure_latency --report     # just re-read audit.log

Sends five Arabic and five English messages of deliberately similar length as
the same person, then reads the `stage` records `agent.audit.log_stage` wrote
and prints mean ms per stage per language.

The pairs below are translations of each other and within a few characters of
the same length, so a difference in the table is a difference in handling the
language, not a difference in how much was asked.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from agent import audit, identity

KHALID = "+97333000003"   # editor @ Hussain Media — internal, has real tasks

PAIRS = [
    ("شنو التاسكات اللي عندي اليوم؟", "What are the tasks I have today?"),
    ("وش ينتظر مراجعتي حاليا؟", "What is waiting for my review now?"),
    ("عطني حالة المشاريع الشغالة", "Give me the status of active projects"),
    ("شنو آخر الملاحظات على النسخة؟", "What are the latest notes on the version?"),
    ("وش المهام اللي متأخرة عندي؟", "Which of my tasks are overdue?"),
]


def _run() -> None:
    from agent import brain

    person = identity.who_is(KHALID)
    if person is None:
        raise SystemExit(f"{KHALID} did not resolve — is the sandbox reachable?")
    phone = identity.tidy(KHALID)

    for arabic, english in PAIRS:
        for message in (arabic, english):
            print(f"  asking: {message}")
            try:
                brain.reply_to(person, message, phone)
            except Exception as broke:
                print(f"    FAILED: {type(broke).__name__}: {broke}")


def _stages() -> list[dict]:
    path = Path(audit.AUDIT_LOG_PATH)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if "stage" in event:
            rows.append(event)
    return rows


def _mean(values: list[float]) -> str:
    return f"{sum(values) / len(values):.0f}" if values else "-"


def report() -> str:
    rows = _stages()
    if not rows:
        return (
            "No stage records in audit.log.\n"
            "Run `python -m tests.measure_latency` against a reachable sandbox "
            "first — an empty table is not a fast one."
        )

    per_stage: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"ar": [], "en": []})
    rounds: dict[str, list[int]] = {"ar": [], "en": []}
    cache = {"cache hit": 0, "live fetch": 0, "unknown number": 0}

    for event in rows:
        stage, detail = event["stage"], (event.get("detail") or "")
        if stage == "identity.who_is":
            cache[detail] = cache.get(detail, 0) + 1
            language = None
        else:
            language = "ar" if "ar" in detail.split() or detail == "ar" else (
                "en" if "en" in detail.split() or detail == "en" else None)

        if stage == "rounds_used":
            used = int(detail.split()[0])
            if language:
                rounds[language].append(used)
            continue

        if stage == "identity.who_is":
            # Not language-specific — it happens once per message, before the
            # message is even read. Reported on its own line below.
            per_stage[stage]["ar"].append(event["duration_ms"])
            continue

        if language:
            per_stage[stage][language].append(event["duration_ms"])

    lines = []
    lines.append(f"{'stage':<24} {'mean ms AR':>12} {'mean ms EN':>12}   {'n AR':>5} {'n EN':>5}")
    lines.append("-" * 66)
    for stage in sorted(per_stage, key=lambda s: (s != "identity.who_is", s)):
        ar, en = per_stage[stage]["ar"], per_stage[stage]["en"]
        if stage == "identity.who_is":
            lines.append(f"{stage:<24} {_mean(ar):>12} {'(same)':>12}   {len(ar):>5} {'-':>5}")
        else:
            lines.append(f"{stage:<24} {_mean(ar):>12} {_mean(en):>12}   {len(ar):>5} {len(en):>5}")

    lines.append("")
    for language in ("ar", "en"):
        used = rounds[language]
        if used:
            lines.append(
                f"rounds used ({language}): mean {sum(used) / len(used):.1f}, "
                f"max {max(used)} of 6 — messages measured: {len(used)}"
            )
    lines.append("")
    lines.append(
        f"identity.who_is: {cache.get('cache hit', 0)} cache hits, "
        f"{cache.get('live fetch', 0)} live fetches "
        f"(the 60s cache is in identity.py, CACHE_SECONDS = {identity.CACHE_SECONDS})"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--report" not in sys.argv:
        _run()
    print()
    print(report())
