"""
In-memory state. A dictionary is genuinely enough for two weeks (Chapter
4) — restarting the server forgets everything. That's an accepted,
documented limitation for this capstone (see README).

Two things live here:
  - conversation history, per phone number
  - a single pending write action per phone number, awaiting a yes/no
    (Phase 3 — "confirm before every write")
"""
from __future__ import annotations

import time

_history: dict[str, list[dict]] = {}
_pending: dict[str, dict] = {}  # phone -> {"tool": ..., "args": ..., "at": ...}

MAX_HISTORY = 24  # keep roughly the last dozen exchanges

# How long a held write waits for its yes. A confirmation is only meaningful
# while the person still remembers what they were asked — a "yes" arriving
# tomorrow morning is answering a question they have long forgotten, and on
# WhatsApp that is an easy accident. Restored from `reem-local-backup`.
# edited by reem — a held write expires instead of waiting forever.
PENDING_SECONDS = 15 * 60


def history_for(phone: str) -> list[dict]:
    return _history.setdefault(phone, [])


def remember(phone: str, role: str, content) -> None:
    history_for(phone).append({"role": role, "content": content})
    if len(_history[phone]) > MAX_HISTORY:
        _history[phone] = _history[phone][-MAX_HISTORY:]


def hold(phone: str, tool: dict, args: dict) -> None:
    _pending[phone] = {"tool": tool, "args": args, "at": time.time()}


def _is_stale(held: dict) -> bool:
    return time.time() - held.get("at", 0) > PENDING_SECONDS


def peek_pending(phone: str) -> dict | None:
    """The write waiting on a yes, or None if there isn't one — including the
    case where one was parked so long ago that it has gone stale. A stale hold
    is dropped rather than run: silence is not consent."""
    held = _pending.get(phone)
    if held is None:
        return None
    if _is_stale(held):
        del _pending[phone]
        return None
    return held


def pop_pending(phone: str) -> dict | None:
    return _pending.pop(phone, None)


def has_pending(phone: str) -> bool:
    return peek_pending(phone) is not None
