"""Stores temporary conversation and pending action data."""

from __future__ import annotations

import time

_history: dict[str, list[dict]] = {}
_pending: dict[str, dict] = {}

MAX_HISTORY = 24
PENDING_SECONDS = 15 * 60


def history_for(phone: str) -> list[dict]:
    """Returns the conversation history for a user."""
    return _history.setdefault(phone, [])


def remember(phone: str, role: str, content) -> None:
    """Adds a message to the user's conversation history."""
    history_for(phone).append({"role": role, "content": content})

    # Keep only the most recent messages.
    if len(_history[phone]) > MAX_HISTORY:
        _history[phone] = _history[phone][-MAX_HISTORY:]


def hold(phone: str, tool: dict, args: dict) -> None:
    """Stores a write action until the user confirms it."""
    _pending[phone] = {
        "tool": tool,
        "args": args,
        "at": time.time(),
    }


def _is_stale(held: dict) -> bool:
    """Checks whether a pending action has expired."""
    return time.time() - held.get("at", 0) > PENDING_SECONDS


def peek_pending(phone: str) -> dict | None:
    """Returns the pending action if it has not expired."""
    held = _pending.get(phone)

    if held is None:
        return None

    # Remove expired actions.
    if _is_stale(held):
        del _pending[phone]
        return None

    return held


def pop_pending(phone: str) -> dict | None:
    """Returns and removes the pending action."""
    return _pending.pop(phone, None)


def has_pending(phone: str) -> bool:
    """Checks whether the user has a pending action."""
    return peek_pending(phone) is not None