"""
Audit trail (Phase 4 — "a log of every tool call"). Appends one JSON line
per tool call to audit.log: who asked, which tool, with what arguments,
what came back (summarized), how long it took, and whether it was
allowed or refused. This is your debugger during the course and — per
the handbook — a compliance requirement in production.

This does NOT replace HiMedia's own audit_log module (that's the system
of record). This is the agent-side record for our own debugging and for
the conversation log the submission checklist asks for.
"""

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
    """One timing record for a stage of answering a single message.

    Written to the same audit.log as the tool calls but with a "stage" key, so
    the two are easy to tell apart when reading the file back. This is
    measurement only — nothing branches on it.
    """
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
    """Tiny context manager for measuring how long a tool call took."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
