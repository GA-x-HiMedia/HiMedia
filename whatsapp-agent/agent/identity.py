"""
Turn a raw phone number into a person the rest of the agent can reason
about. Nothing else happens until this succeeds (Chapter 24).

A phone number is not proof of identity — sender IDs can be spoofed, SIMs
get swapped. A production version of this agent would email a one-time
code the first time it sees a new device before trusting the number. That
is explicitly not required for this capstone (see README's "what is not
finished" section) — but the sandbox lookup here is what stands in for it.
"""
from __future__ import annotations

import re
import time

from . import himedia

_cache: dict[str, tuple[dict, float]] = {}  # phone -> (person, fetched_at)
CACHE_SECONDS = 60


def tidy(raw: str) -> str:
    """whatsapp:+973 3300 0003 -> +97333000003"""
    v = raw.strip()
    if v.lower().startswith("whatsapp:"):
        v = v[9:].strip()
    v = re.sub(r"[\s\-().]", "", v)
    if v.startswith("00"):
        v = "+" + v[2:]
    if not v.startswith("+"):
        v = ("+" + v) if v.startswith("973") else "+973" + v
    return v


def who_is(raw_phone: str) -> dict | None:
    """The person behind this number, or None if HiMedia doesn't know them."""
    phone = tidy(raw_phone)
    hit = _cache.get(phone)
    if hit and time.time() - hit[1] < CACHE_SECONDS:
        return hit[0]

    try:
        person = himedia.get("/v1/permissions/by-phone", phone=phone)
    except himedia.ApiRefused as e:
        if e.code == "USER_NOT_FOUND":
            return None
        raise

    _cache[phone] = (person, time.time())
    return person


def allowed(person: dict, module: str, level: str = "read") -> bool:
    """Does this person hold at least `level` on `module`? Read straight off
    their LIVE permissions map (from the API response) — never from a table
    we maintain ourselves. Write always includes read."""
    granted = person["permissions"].get(module)
    if granted == "write":
        return True
    return granted == "read" and level == "read"
