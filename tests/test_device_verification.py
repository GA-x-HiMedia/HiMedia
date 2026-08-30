"""Device verification tests.

Checks unknown, new, and trusted devices.
"""

from agent import identity

PHONE = "+97333000003"


def _person():
    """Returns a test user."""
    return {
        "user": {
            "full_name": "Khalid Mansoor",
            "phone": PHONE,
            "locale": "ar",
        },
        "company": {
            "id": "cmp_hussain",
            "name": "Hussain Media",
        },
        "role": {"key": "editor"},
        "audience": "internal",
        "permissions": {},
    }


def setup_function(_):
    """Resets device state before each test."""
    identity.forget_device()


def test_an_unknown_device_is_not_trusted():
    assert identity.is_trusted_device(PHONE) is False


def test_first_contact_asks_for_a_code_instead_of_answering():
    reply = identity.device_gate(
        _person(),
        PHONE,
        "شنو التاسكات اللي عندي؟",
    )

    assert reply == identity.ASK_FOR_CODE
    assert identity.is_trusted_device(PHONE) is False


def test_the_code_is_never_the_message_that_asked_for_it():
    code = identity.begin_verification(PHONE)

    assert code not in identity.ASK_FOR_CODE
    assert len(code) == 6
    assert code.isdigit()


def test_the_right_code_verifies_the_device():
    identity.device_gate(_person(), PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]

    reply = identity.device_gate(_person(), PHONE, code)

    assert reply == identity.DEVICE_VERIFIED
    assert identity.is_trusted_device(PHONE) is True


def test_a_verified_device_is_remembered_and_not_asked_again():
    identity.device_gate(_person(), PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(_person(), PHONE, code)

    assert identity.device_gate(
        _person(),
        PHONE,
        "شنو التاسكات؟",
    ) is None

    assert identity.device_gate(
        _person(),
        PHONE,
        "and again",
    ) is None


def test_a_wrong_code_does_not_verify_and_issues_a_fresh_one():
    identity.device_gate(_person(), PHONE, "hello")
    first = identity._pending_codes[identity.tidy(PHONE)][0]

    wrong_code = "000000" if first != "000000" else "111111"

    reply = identity.device_gate(
        _person(),
        PHONE,
        wrong_code,
    )

    assert reply == identity.WRONG_CODE
    assert identity.is_trusted_device(PHONE) is False
    assert identity._pending_codes[identity.tidy(PHONE)][0] != first


def test_an_expired_code_is_refused():
    identity.begin_verification(PHONE)

    phone = identity.tidy(PHONE)
    code, issued_at = identity._pending_codes[phone]

    identity._pending_codes[phone] = (
        code,
        issued_at - identity.CODE_SECONDS - 1,
    )

    assert identity.submit_code(PHONE, code) is False
    assert identity.is_trusted_device(PHONE) is False


def test_verification_is_per_device_not_global():
    other = "+97333000020"

    identity.device_gate(_person(), PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(_person(), PHONE, code)

    assert identity.is_trusted_device(PHONE) is True
    assert identity.is_trusted_device(other) is False


def test_a_number_can_be_untrusted_again():
    identity.device_gate(_person(), PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(_person(), PHONE, code)

    assert identity.is_trusted_device(PHONE) is True

    identity.forget_device(PHONE)

    assert identity.is_trusted_device(PHONE) is False


def test_an_unknown_number_gets_the_refusal_and_never_a_code():
    identity.forget_device()

    reply = identity.device_gate(
        None,
        "+97399999999",
        "hello",
    )

    assert reply == identity.UNKNOWN_NUMBER_REPLY
    assert reply != identity.ASK_FOR_CODE
    assert identity._pending_codes == {}
    assert identity.is_trusted_device("+97399999999") is False

    lowered = reply.lower()

    for tell in ("code", "verif", "رمز", "تحقق"):
        assert tell not in lowered


def test_a_known_number_on_a_first_device_is_challenged():
    identity.forget_device()

    reply = identity.device_gate(
        _person(),
        PHONE,
        "شنو التاسكات اللي عندي؟",
    )

    assert reply == identity.ASK_FOR_CODE
    assert identity.is_trusted_device(PHONE) is False


def test_a_known_number_on_a_remembered_device_goes_straight_through():
    identity.forget_device()

    identity.device_gate(_person(), PHONE, "hello")
    code = identity._pending_codes[identity.tidy(PHONE)][0]
    identity.device_gate(_person(), PHONE, code)

    reply = identity.device_gate(
        _person(),
        PHONE,
        "وش وضع الحملة؟",
    )

    assert reply is None


def test_a_wrong_code_is_refused_and_returns_no_data():
    identity.forget_device()

    identity.device_gate(_person(), PHONE, "hello")
    real = identity._pending_codes[identity.tidy(PHONE)][0]

    wrong_code = "123456" if real != "123456" else "654321"

    reply = identity.device_gate(
        _person(),
        PHONE,
        wrong_code,
    )

    assert reply == identity.WRONG_CODE
    assert identity.is_trusted_device(PHONE) is False
    assert "task" not in reply.lower()
    assert "مهام" not in reply


def test_the_unknown_number_path_end_to_end_sends_only_the_refusal(monkeypatch):
    """Checks the unknown-user flow through WhatsApp."""

    from agent import whatsapp

    identity.forget_device()
    sent = []

    monkeypatch.setattr(
        whatsapp.identity,
        "who_is",
        lambda sender: None,
    )

    monkeypatch.setattr(
        whatsapp,
        "send_whatsapp",
        lambda to, text: sent.append((to, text)),
    )

    whatsapp.think_and_send(
        "97399999999",
        "hello",
    )

    assert len(sent) == 1
    assert sent[0][1] == identity.UNKNOWN_NUMBER_REPLY
    assert identity._pending_codes == {}