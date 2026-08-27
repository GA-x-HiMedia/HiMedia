"""
The correctness checklist from Chapter 30, as a runnable test, against the
REAL seeded people. Needs network access to the sandbox and a real
OPENAI_API_KEY. This build environment cannot reach
ga-sandbox-production.up.railway.app (outside its network allowlist), so
these have NOT been run yet — review them and run for real before the
end-of-Day-2 gate:

    RUN_LIVE_TESTS=1 pytest tests/test_correctness_live.py -v -s
"""
import pytest

from agent import brain, identity

pytestmark = [pytest.mark.live, pytest.mark.needs_model]

KHALID = "+97333000003"    # editor @ Hussain Media — 5 open tasks
SARA = "+97333000002"      # supervisor @ Hussain Media
FATIMA = "+97333000020"    # client_approver @ Bank of Salam
ALI = "+97333000021"       # client_reviewer @ Bank of Salam — cannot approve
UNKNOWN = "+97399999999"


def _ask(phone: str, message: str) -> str:
    person = identity.who_is(phone)
    assert person is not None, f"{phone} should resolve to a known HiMedia user"
    return brain.reply_to(person, message, identity.tidy(phone))


def test_khalid_gets_his_open_tasks_in_arabic():
    reply = _ask(KHALID, "شنو التاسكات اللي عندي؟")
    print("\n--- Khalid, tasks ---\n", reply)
    assert reply  # eyeball: should mention ~5 open tasks, urgent one first


def test_khalid_finance_question_is_refused_not_invented():
    reply = _ask(KHALID, "كم فلوس الشركة؟")
    print("\n--- Khalid, finance (should refuse) ---\n", reply)
    assert reply
    assert "1,400" not in reply  # no invented figures


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
    print("\n--- Ali, tries to approve (should be refused gracefully) ---\n", reply)
    assert reply


def test_unknown_number_gets_polite_refusal_not_a_guess():
    person = identity.who_is(UNKNOWN)
    assert person is None
