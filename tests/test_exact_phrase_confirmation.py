"""
Exact-phrase confirmation for destructive writes.

Harmless confirmations keep the friendly word list — "yes", "تمام", "اوك" and
the rest. A write that cannot be taken back does not: it takes the exact
phrase in `brain.CONFIRM_PHRASE` and nothing else.

Which writes those are is decided from the tool AND its arguments
(`tools.is_destructive`), because the same tool is harmless with one argument
and irreversible with another: moving a task to `in_progress` is ordinary
work, moving it to `cancelled` or `client_review` is not.

These exercise `brain._handle_pending_reply` directly with a stubbed tool, so
nothing here touches the network or needs a model key.

Written by Reem.
"""
import pytest

from agent import brain, memory, tools


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
    source = (brain.__file__)
    with open(source, encoding="utf-8") as f:
        text = f.read()
    # The literal should appear once as the constant definition; everywhere
    # else refers to CONFIRM_PHRASE.
    assert text.count('"' + brain.CONFIRM_PHRASE + '"') == 1


# --- which writes are a point of no return ----------------------------------
#
# The gate is decided from the tool AND its arguments: the same tool is
# harmless with one status and irreversible with another.

DESTRUCTIVE = [
    ("decide_version", {"version_id": "v", "decision": "approve"}),
    ("decide_version", {"version_id": "v", "decision": "request_changes"}),
    ("update_task_status", {"task_id": "t", "status": "client_review"}),
    ("update_task_status", {"task_id": "t", "status": "cancelled"}),
    ("comment_on_task", {"task_id": "t", "body": "x", "client_visible": True}),
]

ORDINARY = [
    ("update_task_status", {"task_id": "t", "status": "todo"}),
    ("update_task_status", {"task_id": "t", "status": "in_progress"}),
    ("update_task_status", {"task_id": "t", "status": "in_review"}),
    ("update_task_status", {"task_id": "t", "status": "done"}),
    ("comment_on_task", {"task_id": "t", "body": "x"}),
    ("comment_on_task", {"task_id": "t", "body": "x", "client_visible": False}),
    ("comment_on_version", {"version_id": "v", "body": "x"}),
]


@pytest.mark.parametrize("name,args", DESTRUCTIVE)
def test_irreversible_and_outward_facing_writes_need_the_phrase(name, args):
    assert tools.is_destructive(name, args) is True
    assert brain.needs_exact_phrase(name, args) is True


@pytest.mark.parametrize("name,args", ORDINARY)
def test_ordinary_writes_keep_the_plain_yes(name, args):
    assert tools.is_destructive(name, args) is False
    assert brain.needs_exact_phrase(name, args) is False


def test_the_same_tool_is_judged_by_its_arguments():
    """The point of deciding on (tool, args) rather than on the tool alone."""
    harmless = {"task_id": "t", "status": "in_progress"}
    final = {"task_id": "t", "status": "cancelled"}

    assert tools.is_destructive("update_task_status", harmless) is False
    assert tools.is_destructive("update_task_status", final) is True


def test_reads_never_need_the_phrase():
    for tool in tools.ALL_TOOLS:
        if not tool["writes"]:
            assert tools.is_destructive(tool["function"]["name"], {}) is False


def test_an_unclassified_or_unknown_tool_fails_towards_asking():
    """A missed classification must fail towards asking, never towards acting."""
    assert tools.is_destructive("some_tool_added_later", {"task_id": "t"}) is True


def test_every_write_tool_declares_whether_it_is_destructive():
    """The guard that keeps this honest: a new write tool cannot be added
    without someone deciding which side of the line it falls on."""
    undeclared = [
        t["function"]["name"] for t in tools.ALL_TOOLS
        if t["writes"] and "destructive" not in t
    ]
    assert undeclared == [], f"write tools with no `destructive` key: {undeclared}"


def test_cancelling_a_task_takes_the_phrase_end_to_end():
    """The full flow for the nearest thing to a delete this API has."""
    tool, calls = _tool("update_task_status")
    memory.hold(PHONE, tool, {"task_id": "tsk_0001", "status": "cancelled"})

    reply = brain._handle_pending_reply(
        _person(), PHONE, "yes", memory.peek_pending(PHONE))

    assert len(calls) == 0, "'yes' must not cancel a task"
    assert "cancelled" in reply.lower()

    memory.hold(PHONE, tool, {"task_id": "tsk_0001", "status": "cancelled"})
    brain._handle_pending_reply(
        _person(), PHONE, brain.CONFIRM_PHRASE, memory.peek_pending(PHONE))

    assert len(calls) == 1, "the phrase should carry it through"


def test_sending_work_to_a_client_takes_the_phrase_end_to_end():
    tool, calls = _tool("update_task_status")
    memory.hold(PHONE, tool, {"task_id": "tsk_0001", "status": "client_review"})

    brain._handle_pending_reply(_person(), PHONE, "تمام", memory.peek_pending(PHONE))

    assert len(calls) == 0, "you cannot un-send work to a client"


def test_moving_a_task_along_internally_still_takes_a_plain_yes():
    tool, calls = _tool("update_task_status")
    memory.hold(PHONE, tool, {"task_id": "tsk_0001", "status": "in_progress"})

    brain._handle_pending_reply(_person(), PHONE, "yes", memory.peek_pending(PHONE))

    assert len(calls) == 1, "ordinary work must not need a typed phrase"
