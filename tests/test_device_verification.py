"""
TEMP (Sara's task) — first-device verification.

Sara owns OTP / device verification. It was missing from `main` and from her
branch when Step 8 checked, so this covers the smallest working version added
to `agent/identity.py` in the meantime. Delete this file along with that block
when Sara's own implementation lands.

No network: the gate is pure logic over an in-memory set.
"""
from agent import identity

PHONE = "+97333000003"


def setup_function(_):
    identity.forget_device()


def test_an_unknown_device_is_not_trusted():
    assert identity.is_trusted_device(PHONE) is False


def test_first_contact_asks_for_a_code_instead_of_answering():
    reply = identity.device_gate(PHONE, "شنو التاسكات اللي عندي؟")

    assert reply == identity.ASK_FOR_CODE
    assert identity.is_trusted_device(PHONE) is False


def test_the_code_is_never_the_message_that_asked_for_it():
    """Sending the code over the same WhatsApp thread would prove nothing —
    whoever holds the number would just read it back."""
    code = identity.begin_verification(PHONE)

    assert code not in identity.ASK_FOR_CODE
    assert len(code) == 6 and code.isdigit()


def test_the_right_code_verifies_the_device():
    identity.device_gate(PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]

    reply = identity.device_gate(PHONE, code)

    assert reply == identity.DEVICE_VERIFIED
    assert identity.is_trusted_device(PHONE) is True


def test_a_verified_device_is_remembered_and_not_asked_again():
    identity.device_gate(PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(PHONE, code)

    # None means "trusted, handle this message normally".
    assert identity.device_gate(PHONE, "شنو التاسكات؟") is None
    assert identity.device_gate(PHONE, "and again") is None


def test_a_wrong_code_does_not_verify_and_issues_a_fresh_one():
    identity.device_gate(PHONE, "hello")
    first = identity._pending_codes[identity.tidy(PHONE)][0]

    reply = identity.device_gate(PHONE, "000000" if first != "000000" else "111111")

    assert reply == identity.WRONG_CODE
    assert identity.is_trusted_device(PHONE) is False
    assert identity._pending_codes[identity.tidy(PHONE)][0] != first


def test_an_expired_code_is_refused():
    identity.begin_verification(PHONE)
    phone = identity.tidy(PHONE)
    code, issued_at = identity._pending_codes[phone]
    identity._pending_codes[phone] = (code, issued_at - identity.CODE_SECONDS - 1)

    assert identity.submit_code(PHONE, code) is False
    assert identity.is_trusted_device(PHONE) is False


def test_verification_is_per_device_not_global():
    other = "+97333000020"
    identity.device_gate(PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(PHONE, code)

    assert identity.is_trusted_device(PHONE) is True
    assert identity.is_trusted_device(other) is False


def test_a_number_can_be_untrusted_again():
    identity.device_gate(PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(PHONE, code)
    assert identity.is_trusted_device(PHONE) is True

    identity.forget_device(PHONE)

    assert identity.is_trusted_device(PHONE) is False
