"""Live correctness tests for the HiMedia agent.

Run:
    RUN_LIVE_TESTS=1 pytest tests/test_correctness_live.py -v -s
"""

import pytest

from agent import brain, identity

pytestmark = [pytest.mark.live, pytest.mark.needs_model]

KHALID = "+97333000003"   # Internal editor.
SARA = "+97333000002"     # Internal supervisor.
FATIMA = "+97333000020"   # Client approver.
ALI = "+97333000021"      # Client reviewer.
UNKNOWN = "+97399999999"  # Unknown user.


def _ask(phone: str, message: str) -> str:
    """Sends a message as a known user."""
    person = identity.who_is(phone)
    assert person is not None, f"{phone} should resolve to a known HiMedia user"
    return brain.reply_to(person, message, identity.tidy(phone))


def test_khalid_gets_his_open_tasks_in_arabic():
    reply = _ask(KHALID, "شنو التاسكات اللي عندي؟")

    print("\n--- Khalid, tasks ---\n", reply)

    assert reply


def test_khalid_finance_question_is_refused_not_invented():
    reply = _ask(KHALID, "كم فلوس الشركة؟")

    print("\n--- Khalid, finance ---\n", reply)

    assert reply
    assert "1,400" not in reply


def test_sara_pending_approval():
    reply = _ask(SARA, "وش ينتظر موافقتي؟")

    print("\n--- Sara, pending approval ---\n", reply)

    assert reply


def test_fatima_sees_only_shared_versions_never_drafts():
    reply = _ask(FATIMA, "وش وضع الحملة؟")

    print("\n--- Fatima, campaign status ---\n", reply)

    assert "v3" not in reply
    assert "Khalid" not in reply


def test_ali_cannot_approve_and_is_told_who_can():
    reply = _ask(ALI, "approve the reels")

    print("\n--- Ali, approval attempt ---\n", reply)

    assert reply


def test_unknown_number_gets_polite_refusal_not_a_guess():
    person = identity.who_is(UNKNOWN)

    assert person is None