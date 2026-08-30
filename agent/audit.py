"""Logs tool calls and response timing for auditing and debugging."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path("audit.log")


def log_tool_call(
    *,
    phone: str,
    name: str,
    role: str,
    tool: str,
    args: dict,
    result_summary: str,
    duration_ms: float,
    allowed: bool,
) -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phone": phone,
        "name": name,
        "role": role,
        "tool": tool,
        "args": args,
        "result_summary": result_summary[:300],
        "duration_ms": round(duration_ms, 1),
        "allowed": allowed,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def log_stage(
    *,
    phone: str,
    stage: str,
    duration_ms: float,
    detail: str = "",
) -> None:
    """Logs the duration of a processing stage."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phone": phone,
        "stage": stage,
        "duration_ms": round(duration_ms, 1),
        "detail": detail,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


class Timer:
    """Measures execution time."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000