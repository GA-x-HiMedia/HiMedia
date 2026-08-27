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
    we maintain ourselves. Write always includes read.

    The owner role is the one whose permission map arrives empty from
    /v1/roles while meaning "everything". by-phone expands it for us, but we
    honour is_owner too so the answer never depends on which endpoint the
    caller happened to read.
    """
    if person.get("role", {}).get("is_owner"):
        return True

    granted = person.get("permissions", {}).get(module)  # missing means "none"
    if granted == "write":
        return True
    return granted == "read" and level == "read"


def is_client(person: dict) -> bool:
    """Client staff live in a different world of data from the production
    company. Every audience decision in tools.py keys off this."""
    return person.get("audience") == "client"


def phone_of(person: dict) -> str:
    """The number every API call is filtered by.

    It comes from the identity lookup, never from a tool argument — the model
    must never get to choose whose data is fetched.
    """
    return person["user"]["phone"]


def forget(raw_phone: str | None = None) -> None:
    """Drop a cached lookup. Used by tests, and after moving a number onto a
    different account mid-demo."""
    if raw_phone is None:
        _cache.clear()
    else:
        _cache.pop(tidy(raw_phone), None)


_colleagues: dict[tuple[str, str, str], tuple[list[str], float]] = {}


def colleagues_who_can(person: dict, module: str, level: str = "write") -> list[str]:
    """Names of people at the caller's OWN company who hold this permission.

    A refusal is more use when it ends with a name. Only ever looks inside the
    caller's own company, so it can never become a way of learning who works
    at another one — a client asking who can approve must never be handed a
    production-company staff list.
    """
    company_id = person["company"]["id"]
    key = (company_id, module, level)

    hit = _colleagues.get(key)
    if hit and time.time() - hit[1] < CACHE_SECONDS:
        return hit[0]

    roles = {role["key"]: role for role in himedia.list_roles()}
    names = []
    for user in himedia.list_users(company_id=company_id):
        if user["id"] == person["user"]["id"] or not user.get("is_active", True):
            continue
        role = roles.get(user.get("role_key"), {})
        pretend = {"role": role, "permissions": role.get("permissions", {})}
        if allowed(pretend, module, level):
            names.append(user["full_name"])

    _colleagues[key] = (names, time.time())
    return names


def describe(person: dict) -> str:
    """One line for logs and for the terminal banner."""
    user = person["user"]
    return (
        f"{user['full_name']} · {person['role']['key']} · "
        f"{person['company']['name']} · {person['audience']}"
    )


# What to say to a number we do not recognise. Polite, brief, and then stop:
# do not offer to look anything up, do not guess who they might be, and do not
# fall back to a "public" mode. An unknown number gets nothing.
UNKNOWN_NUMBER_REPLY = (
    "ما لقيت رقمك في نظام HiMedia. "
    "كلّم مسؤول الحساب عندكم عشان يضيفك.\n"
    "I could not find your number in the HiMedia system. "
    "Please ask your account administrator to add you."
)
