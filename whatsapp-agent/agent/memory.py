"""
In-memory conversation history. A dictionary is genuinely enough for two
weeks (Chapter 4) — restarting the server forgets everything, an accepted,
documented limitation for this capstone.

Phase 3 will add a second piece of state here: a pending write action
awaiting yes/no confirmation. Not needed yet — there are no write tools
in the Phase 2 catalogue for anything to be pending on.
"""
from __future__ import annotations

_history: dict[str, list[dict]] = {}
MAX_HISTORY = 24  # keep roughly the last dozen exchanges


def history_for(phone: str) -> list[dict]:
    return _history.setdefault(phone, [])


def remember(phone: str, role: str, content) -> None:
    history_for(phone).append({"role": role, "content": content})
    if len(_history[phone]) > MAX_HISTORY:
        _history[phone] = _history[phone][-MAX_HISTORY:]
