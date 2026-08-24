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

_history: dict[str, list[dict]] = {}
_pending: dict[str, dict] = {}  # phone -> {"tool": <tool dict>, "args": dict}

MAX_HISTORY = 24  # keep roughly the last dozen exchanges


def history_for(phone: str) -> list[dict]:
    return _history.setdefault(phone, [])


def remember(phone: str, role: str, content) -> None:
    history_for(phone).append({"role": role, "content": content})
    if len(_history[phone]) > MAX_HISTORY:
        _history[phone] = _history[phone][-MAX_HISTORY:]


def hold(phone: str, tool: dict, args: dict) -> None:
    _pending[phone] = {"tool": tool, "args": args}


def peek_pending(phone: str) -> dict | None:
    return _pending.get(phone)


def pop_pending(phone: str) -> dict | None:
    return _pending.pop(phone, None)


def has_pending(phone: str) -> bool:
    return phone in _pending
