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

import logging
import re
import secrets
import time

from . import audit, himedia

logger = logging.getLogger(__name__)

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
        audit.log_stage(phone=phone, stage="identity.who_is", duration_ms=0.0,
                        detail="cache hit")
        return hit[0]

    with audit.Timer() as t:
        try:
            person = himedia.get_permissions(phone)
        except himedia.ApiRefused as e:
            if e.code == "USER_NOT_FOUND":
                audit.log_stage(phone=phone, stage="identity.who_is",
                                duration_ms=t_elapsed(t), detail="unknown number")
                return None
            raise

    audit.log_stage(phone=phone, stage="identity.who_is", duration_ms=t.elapsed_ms,
                    detail="live fetch")
    _cache[phone] = (person, time.time())
    return person


def t_elapsed(timer) -> float:
    """The Timer only sets elapsed_ms on exit; inside an except block it may
    not be set yet."""
    return getattr(timer, "elapsed_ms", 0.0)


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


# edited by reem — helpers below: is_client, phone_of, forget,
# colleagues_who_can, describe, UNKNOWN_NUMBER_REPLY.
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


# --- TEMP (Sara's task): first-device verification --------------------------
#
# This is Sara's area, implemented at the smallest size that actually works so
# the gate is not simply missing. Replace it with hers when it lands.
#
# A phone number is not proof of identity: sender IDs can be spoofed and SIMs
# get swapped, and until now this project trusted a number the moment the API
# recognised it. The first time an unknown device contacts us we now issue a
# one-time code and answer nothing else until it comes back.
#
# The code is delivered OUT OF BAND — to the server log here, which stands in
# for the email a production version would send. Sending it over the same
# WhatsApp thread would prove nothing at all: whoever holds the number would
# simply read it. That is the one part of this worth keeping whatever else
# changes.
#
# In memory, like everything else in this project (README, "what's not
# finished"): a restart asks everyone to verify again.

_verified_devices: set[str] = set()
_pending_codes: dict[str, tuple[str, float]] = {}

CODE_SECONDS = 10 * 60


def is_trusted_device(raw_phone: str) -> bool:
    return tidy(raw_phone) in _verified_devices


def begin_verification(raw_phone: str) -> str:
    """Issue a fresh code for this number and return it for out-of-band
    delivery. Any previous unused code stops working."""
    phone = tidy(raw_phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    _pending_codes[phone] = (code, time.time())
    # The code itself never goes to audit.log — that file is a record of what
    # happened, not a place to keep secrets.
    audit.log_stage(phone=phone, stage="identity.verification",
                    duration_ms=0.0, detail="code issued")
    logger.warning("Verification code for %s: %s (deliver out of band)", phone, code)
    return code


def submit_code(raw_phone: str, submitted: str) -> bool:
    """True if this is the right code, in time. A correct code trusts the
    device from now on; a wrong one burns nothing, but an expired one is gone."""
    phone = tidy(raw_phone)
    held = _pending_codes.get(phone)
    if held is None:
        return False

    code, issued_at = held
    if time.time() - issued_at > CODE_SECONDS:
        del _pending_codes[phone]
        return False

    if not secrets.compare_digest(submitted.strip(), code):
        return False

    del _pending_codes[phone]
    _verified_devices.add(phone)
    audit.log_stage(phone=phone, stage="identity.verification",
                    duration_ms=0.0, detail="device verified")
    return True


def forget_device(raw_phone: str | None = None) -> None:
    """Drop a device's verified status. Used by tests, and when a number is
    reported lost."""
    if raw_phone is None:
        _verified_devices.clear()
        _pending_codes.clear()
        return
    phone = tidy(raw_phone)
    _verified_devices.discard(phone)
    _pending_codes.pop(phone, None)


ASK_FOR_CODE = (
    "أول مرة أشوف هذا الجهاز. أرسلت لك رمز تحقق من ستة أرقام — اكتبه هني عشان أكمل.\n"
    "First time I've seen this device. I've sent you a six-digit verification "
    "code — reply with it to continue."
)

WRONG_CODE = (
    "الرمز مو صحيح أو انتهت صلاحيته. أرسلت لك رمز جديد.\n"
    "That code was wrong or expired. I've sent a new one."
)

DEVICE_VERIFIED = (
    "تم التحقق من جهازك. تفضل، شنو تحتاج؟\n"
    "Device verified. What do you need?"
)


def device_gate(raw_phone: str, message: str) -> str | None:
    """The whole gate, in one call, so the callers stay thin.

    Returns None when the device is trusted and the message should be handled
    normally. Otherwise returns the reply to send instead.
    """
    if is_trusted_device(raw_phone):
        return None

    phone = tidy(raw_phone)
    if phone in _pending_codes:
        if submit_code(phone, message):
            return DEVICE_VERIFIED
        begin_verification(phone)
        return WRONG_CODE

    begin_verification(phone)
    return ASK_FOR_CODE
