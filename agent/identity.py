"""Handles user identity, permissions, and device verification."""

from __future__ import annotations

import logging
import re
import secrets
import time

from . import audit, himedia

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[dict, float]] = {}  # Cached identity lookups.
CACHE_SECONDS = 60


def tidy(raw: str) -> str:
    """Normalizes a phone number."""
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
    """Returns the person linked to this phone number."""
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
    """Returns elapsed time safely."""
    return getattr(timer, "elapsed_ms", 0.0)


def allowed(person: dict, module: str, level: str = "read") -> bool:
    """Checks whether a user has the required permission."""
    if person.get("role", {}).get("is_owner"):
        return True

    granted = person.get("permissions", {}).get(module)  # missing means "none"
    if granted == "write":
        return True
    return granted == "read" and level == "read"


def is_client(person: dict) -> bool:
    """Returns whether the user is a client."""
    return person.get("audience") == "client"


def phone_of(person: dict) -> str:
    """Returns the verified phone number from the user's identity."""
    return person["user"]["phone"]


def forget(raw_phone: str | None = None) -> None:
    """Clears cached identity data."""
    if raw_phone is None:
        _cache.clear()
    else:
        _cache.pop(tidy(raw_phone), None)


def describe(person: dict) -> str:
    """Returns a short description of the user."""
    user = person["user"]
    return (
        f"{user['full_name']} · {person['role']['key']} · "
        f"{person['company']['name']} · {person['audience']}"
    )


# Reply used when the phone number is not recognized.
UNKNOWN_NUMBER_REPLY = (
    "ما لقيت رقمك في نظام HiMedia. "
    "كلّم مسؤول الحساب عندكم عشان يضيفك.\n"
    "I could not find your number in the HiMedia system. "
    "Please ask your account administrator to add you."
)


# First-device verification.

_verified_devices: set[str] = set()
_pending_codes: dict[str, tuple[str, float]] = {}

CODE_SECONDS = 10 * 60


def is_trusted_device(raw_phone: str) -> bool:
    """Checks whether the device has been verified."""
    return tidy(raw_phone) in _verified_devices


def begin_verification(raw_phone: str) -> str:
    """Creates a new verification code."""   
    phone = tidy(raw_phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    _pending_codes[phone] = (code, time.time())
    # Do not store verification codes in the audit log.
    audit.log_stage(phone=phone, stage="identity.verification",
                    duration_ms=0.0, detail="code issued")
    logger.warning("Verification code for %s: %s (deliver out of band)", phone, code)
    return code


def submit_code(raw_phone: str, submitted: str) -> bool:
    """Verifies a submitted code and trusts the device if valid."""
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
    """Removes a device's verification status."""
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


def device_gate(person: dict | None, raw_phone: str, message: str) -> str | None:
    """Handles unknown users and first-device verification.

    Returns None when normal processing can continue.
    """
    if person is None:
        # Unknown users receive no system information.

        return UNKNOWN_NUMBER_REPLY

    if is_trusted_device(raw_phone):
        return None

    phone = tidy(raw_phone)

    if phone in _pending_codes:
        # Verify the submitted code.
        if submit_code(phone, message):
            return DEVICE_VERIFIED
        begin_verification(phone)
        return WRONG_CODE

    # Start verification for a new device.
    begin_verification(phone)
    return ASK_FOR_CODE
