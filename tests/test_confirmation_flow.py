"""
Confirmation flow tests.

Checks that pending write actions are confirmed, cancelled, or kept
pending correctly. Uses a fake tool, so no network or API key is needed.
"""

from agent import brain, memory


def _fake_tool(writes: bool = True):
    """Creates a fake tool for testing."""

    calls = []

    def _run(person, args):
        calls.append((person, args))
        return {"ok": True}

    tool = {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "test",
            "parameters": {},
        },
        "needs": ("tasks", "write"),
        "audience": "internal",
        "writes": writes,
        "run": _run,
    }

    return tool, calls


def _person():
    """Creates a test user with write permission."""

    return {
        "user": {
            "full_name": "Test User",
            "phone": "+97333099999",
            "locale": "en",
        },
        "company": {
            "id": "cmp_test",
            "name": "Test Co",
            "kind": "media_company",
        },
        "role": {
            "key": "editor",
            "name": "editor",
        },
        "audience": "internal",
        "permissions": {"tasks": "write"},
        "counts": {},
    }


def setup_function(_):
    """Clears shared state before each test."""

    memory._history.clear()
    memory._pending.clear()


def test_affirmative_reply_runs_the_held_action():
    phone = "+97333099999"
    tool, calls = _fake_tool()

    memory.hold(
        phone,
        tool,
        {"task_id": "tsk_0001", "status": "done"},
    )

    reply = brain._handle_pending_reply(
        _person(),
        phone,
        "yes",
        memory.peek_pending(phone),
    )

    assert len(calls) == 1
    assert not memory.has_pending(phone)
    assert "Done" in reply or "تم" in reply


def test_negative_reply_discards_without_running():
    phone = "+97333099999"
    tool, calls = _fake_tool()

    memory.hold(
        phone,
        tool,
        {"task_id": "tsk_0001", "status": "done"},
    )

    reply = brain._handle_pending_reply(
        _person(),
        phone,
        "no",
        memory.peek_pending(phone),
    )

    assert len(calls) == 0
    assert not memory.has_pending(phone)
    assert "Cancelled" in reply or "إلغاء" in reply


def test_ambiguous_reply_neither_runs_nor_drops_the_pending_action():
    phone = "+97333099999"
    tool, calls = _fake_tool()

    memory.hold(
        phone,
        tool,
        {"task_id": "tsk_0001", "status": "done"},
    )

    reply = brain._handle_pending_reply(
        _person(),
        phone,
        "what do you mean",
        memory.peek_pending(phone),
    )

    assert len(calls) == 0
    assert memory.has_pending(phone)
    assert "pending" in reply.lower() or "معلّق" in reply


def test_arabic_affirmatives_are_recognised():
    phone = "+97333099999"

    for word in ["أي", "ايوه", "نعم", "تمام"]:
        tool, calls = _fake_tool()

        memory.hold(
            phone,
            tool,
            {"task_id": "tsk_0001", "status": "done"},
        )

        brain._handle_pending_reply(
            _person(),
            phone,
            word,
            memory.peek_pending(phone),
        )

        assert len(calls) == 1, (
            f"{word!r} should have been recognised as affirmative"
        )