"""
Exact-phrase confirmation for destructive writes (Step 7).

Harmless confirmations keep the friendly word list — "yes", "تمام", "اوك" and
the rest. `decide_version` does not: it decides something on the client's
behalf and there is no undo, so it takes the exact phrase in
`brain.CONFIRM_PHRASE` and nothing else.

These exercise `brain._handle_pending_reply` directly with a stubbed tool, so
nothing here touches the network or needs a model key.
"""
import pytest

from agent import brain, memory


def _tool(name: str):
    calls = []

    def _run(person, args):
        calls.append((person, args))
        return {"ok": True}

    return {
        "type": "function",
        "function": {"name": name, "description": "test", "parameters": {}},
        "needs": ("reviews", "write") if name == "decide_version" else ("tasks", "write"),
        "audience": "both" if name == "decide_version" else "internal",
        "writes": True,
        "run": _run,
    }, calls


def _person(locale: str = "en"):
    return {
        "user": {"full_name": "Test User", "phone": "+97333099999", "locale": locale},
        "company": {"id": "cmp_test", "name": "Test Co", "kind": "media_company"},
        "role": {"key": "editor", "name": "editor"},
        "audience": "internal",
        "permissions": {"tasks": "write", "reviews": "write"},
        "counts": {},
    }


PHONE = "+97333099999"


def setup_function(_):
    memory._history.clear()
    memory._pending.clear()


def _answer(reply_text: str, tool_name: str = "decide_version", locale: str = "en"):
    tool, calls = _tool(tool_name)
    memory.hold(PHONE, tool, {"version_id": "ver_reels_v2", "decision": "approve"})
    reply = brain._handle_pending_reply(
        _person(locale), PHONE, reply_text, memory.peek_pending(PHONE))
    return reply, calls


def test_the_exact_phrase_approves():
    reply, calls = _answer(brain.CONFIRM_PHRASE)

    assert len(calls) == 1, "the exact phrase should run the held action"
    assert not memory.has_pending(PHONE)
    assert "Done" in reply or "تم" in reply


def test_the_exact_phrase_is_accepted_with_surrounding_whitespace():
    reply, calls = _answer(f"  {brain.CONFIRM_PHRASE}  ")

    assert len(calls) == 1, "trailing whitespace is a typing artefact, not a different answer"


@pytest.mark.parametrize("reply_text", ["ok", "تمام", "yes", "اي", "نعم", "sure"])
def test_a_plain_yes_cancels_a_destructive_write(reply_text):
    """The whole point: these still confirm harmless writes, and must not
    confirm this one."""
    reply, calls = _answer(reply_text)

    assert len(calls) == 0, f"{reply_text!r} must not approve a version"
    assert not memory.has_pending(PHONE), "an unconfirmed destructive write is cancelled, not left pending"
    assert "cancelled" in reply.lower()
    assert brain.CONFIRM_PHRASE in reply, "the message must say what to type instead"


def test_an_empty_reply_cancels():
    reply, calls = _answer("")

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)
    assert "cancelled" in reply.lower()


def test_a_partial_match_cancels():
    partial = brain.CONFIRM_PHRASE.split()[0]      # "تأكيد" alone
    assert partial and partial != brain.CONFIRM_PHRASE

    reply, calls = _answer(partial)

    assert len(calls) == 0, "a partial phrase is not the phrase"
    assert not memory.has_pending(PHONE)
    assert "cancelled" in reply.lower()


def test_a_longer_phrase_containing_it_cancels():
    """Substring matching would defeat the point — the model, or the person,
    could wrap it in a sentence."""
    reply, calls = _answer(f"من فضلك {brain.CONFIRM_PHRASE} الحين")

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)


def test_the_arabic_cancellation_message_is_used_for_an_arabic_speaker():
    reply, calls = _answer("ok", locale="ar")

    assert len(calls) == 0
    assert brain.CONFIRM_PHRASE in reply
    assert "ألغيت" in reply


def test_harmless_writes_still_take_a_plain_yes():
    """Step 7 keeps the friendly list for everything that is not destructive."""
    for word in ["yes", "ok", "تمام", "اي"]:
        setup_function(None)
        reply, calls = _answer(word, tool_name="update_task_status")
        assert len(calls) == 1, f"{word!r} should still confirm a harmless write"


def test_the_phrase_lives_in_exactly_one_place():
    """A second copy of the string is how these gates rot — the message tells
    people to type one thing and the check compares against another."""
    assert brain.needs_exact_phrase("decide_version")
    assert not brain.needs_exact_phrase("update_task_status")
    assert not brain.needs_exact_phrase("comment_on_task")
    assert not brain.needs_exact_phrase("comment_on_version")

    source = (brain.__file__)
    with open(source, encoding="utf-8") as f:
        text = f.read()
    # The literal should appear once as the constant definition; everywhere
    # else refers to CONFIRM_PHRASE.
    assert text.count('"' + brain.CONFIRM_PHRASE + '"') == 1
