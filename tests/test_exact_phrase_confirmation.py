"""Tests exact confirmation for destructive writes."""

import pytest

from agent import brain, memory, tools

PHONE = "+97333099999"


def _tool(name: str):
    """Returns a test write tool and its recorded calls."""
    calls = []

    def _run(person, args):
        calls.append((person, args))
        return {"ok": True}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "test",
            "parameters": {},
        },
        "needs": (
            ("reviews", "write")
            if name == "decide_version"
            else ("tasks", "write")
        ),
        "audience": (
            "both"
            if name == "decide_version"
            else "internal"
        ),
        "writes": True,
        "run": _run,
    }, calls


def _person(locale: str = "en"):
    """Returns a test user."""
    return {
        "user": {
            "full_name": "Test User",
            "phone": PHONE,
            "locale": locale,
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
        "permissions": {
            "tasks": "write",
            "reviews": "write",
        },
        "counts": {},
    }


def setup_function(_):
    """Resets shared memory before each test."""
    memory._history.clear()
    memory._pending.clear()


def _answer(
    reply_text: str,
    tool_name: str = "decide_version",
    locale: str = "en",
):
    """Runs a confirmation reply against a held action."""
    tool, calls = _tool(tool_name)

    memory.hold(
        PHONE,
        tool,
        {
            "version_id": "ver_reels_v2",
            "decision": "approve",
        },
    )

    reply = brain._handle_pending_reply(
        _person(locale),
        PHONE,
        reply_text,
        memory.peek_pending(PHONE),
    )

    return reply, calls


def test_the_exact_phrase_approves():
    reply, calls = _answer(brain.CONFIRM_PHRASE)

    assert len(calls) == 1
    assert not memory.has_pending(PHONE)
    assert "Done" in reply or "تم" in reply


def test_the_exact_phrase_is_accepted_with_surrounding_whitespace():
    reply, calls = _answer(f"  {brain.CONFIRM_PHRASE}  ")

    assert len(calls) == 1


def test_the_english_phrase_also_approves():
    """An English speaker should not need an Arabic keyboard to approve
    something. The gate works because the phrase cannot be typed by reflex,
    not because of which script it is written in."""
    reply, calls = _answer(brain.CONFIRM_PHRASE_EN)

    assert len(calls) == 1
    assert not memory.has_pending(PHONE)


def test_the_english_phrase_is_not_case_sensitive():
    reply, calls = _answer(brain.CONFIRM_PHRASE_EN.lower())

    assert len(calls) == 1


def test_either_phrase_works_whatever_language_they_write_in():
    """Both are always accepted. Only the phrase we ASK for changes."""
    assert brain.is_confirm_phrase(brain.CONFIRM_PHRASE)
    assert brain.is_confirm_phrase(brain.CONFIRM_PHRASE_EN)
    assert brain.phrase_for("ar") == brain.CONFIRM_PHRASE
    assert brain.phrase_for("en") == brain.CONFIRM_PHRASE_EN


def test_near_misses_of_the_english_phrase_still_cancel():
    for text in ("FINAL", "CONFIRMATION", "final confirm",
                 "I give FINAL CONFIRMATION now"):
        assert not brain.is_confirm_phrase(text), text


@pytest.mark.parametrize(
    "reply_text",
    ["ok", "تمام", "yes", "اي", "نعم", "sure"],
)
def test_a_plain_yes_cancels_a_destructive_write(reply_text):
    reply, calls = _answer(reply_text)

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)

    if any("\u0600" <= ch <= "\u06ff" for ch in reply_text):
        assert "ألغيت" in reply
    else:
        assert "cancelled" in reply.lower()

    # The reply must name a phrase that actually works, in their language.
    assert brain.phrase_for(brain._language_of(reply_text)) in reply


def test_an_empty_reply_cancels():
    reply, calls = _answer("")

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)
    assert "cancelled" in reply.lower()


def test_a_partial_match_cancels():
    partial = brain.CONFIRM_PHRASE.split()[0]

    assert partial
    assert partial != brain.CONFIRM_PHRASE

    reply, calls = _answer(partial)

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)
    assert "ألغيت" in reply
    # The reply must name a phrase that actually works, in their language.
    assert brain.phrase_for(brain._language_of(partial)) in reply


def test_a_longer_phrase_containing_it_cancels():
    reply, calls = _answer(
        f"من فضلك {brain.CONFIRM_PHRASE} الحين"
    )

    assert len(calls) == 0
    assert not memory.has_pending(PHONE)


def test_the_arabic_cancellation_message_is_used_for_an_arabic_speaker():
    reply, calls = _answer("تمام", locale="ar")

    assert len(calls) == 0
    # An Arabic speaker is asked for the Arabic phrase.
    assert brain.CONFIRM_PHRASE in reply
    assert "ألغيت" in reply


def test_harmless_writes_still_take_a_plain_yes():
    for word in ["yes", "ok", "تمام", "اي"]:
        setup_function(None)

        reply, calls = _answer(
            word,
            tool_name="update_task_status",
        )

        assert len(calls) == 1


def test_the_phrase_lives_in_exactly_one_place():
    """Checks that the confirmation phrase has one source."""

    source = brain.__file__

    with open(source, encoding="utf-8") as f:
        text = f.read()

    assert text.count(
        '"' + brain.CONFIRM_PHRASE + '"'
    ) == 1


DESTRUCTIVE = [
    (
        "decide_version",
        {"version_id": "v", "decision": "approve"},
    ),
    (
        "decide_version",
        {"version_id": "v", "decision": "request_changes"},
    ),
    (
        "update_task_status",
        {"task_id": "t", "status": "client_review"},
    ),
    (
        "update_task_status",
        {"task_id": "t", "status": "cancelled"},
    ),
    (
        "comment_on_task",
        {
            "task_id": "t",
            "body": "x",
            "client_visible": True,
        },
    ),
]


ORDINARY = [
    (
        "update_task_status",
        {"task_id": "t", "status": "todo"},
    ),
    (
        "update_task_status",
        {"task_id": "t", "status": "in_progress"},
    ),
    (
        "update_task_status",
        {"task_id": "t", "status": "in_review"},
    ),
    (
        "update_task_status",
        {"task_id": "t", "status": "done"},
    ),
    (
        "comment_on_task",
        {"task_id": "t", "body": "x"},
    ),
    (
        "comment_on_task",
        {
            "task_id": "t",
            "body": "x",
            "client_visible": False,
        },
    ),
    (
        "comment_on_version",
        {"version_id": "v", "body": "x"},
    ),
]


@pytest.mark.parametrize("name,args", DESTRUCTIVE)
def test_irreversible_and_outward_facing_writes_need_the_phrase(
    name,
    args,
):
    assert tools.is_destructive(name, args) is True
    assert brain.needs_exact_phrase(name, args) is True


@pytest.mark.parametrize("name,args", ORDINARY)
def test_ordinary_writes_keep_the_plain_yes(name, args):
    assert tools.is_destructive(name, args) is False
    assert brain.needs_exact_phrase(name, args) is False


def test_the_same_tool_is_judged_by_its_arguments():
    harmless = {
        "task_id": "t",
        "status": "in_progress",
    }

    destructive = {
        "task_id": "t",
        "status": "cancelled",
    }

    assert tools.is_destructive(
        "update_task_status",
        harmless,
    ) is False

    assert tools.is_destructive(
        "update_task_status",
        destructive,
    ) is True


def test_reads_never_need_the_phrase():
    for tool in tools.ALL_TOOLS:
        if not tool["writes"]:
            assert tools.is_destructive(
                tool["function"]["name"],
                {},
            ) is False


def test_an_unclassified_or_unknown_tool_fails_towards_asking():
    assert tools.is_destructive(
        "some_tool_added_later",
        {"task_id": "t"},
    ) is True


def test_every_write_tool_declares_whether_it_is_destructive():
    undeclared = [
        tool["function"]["name"]
        for tool in tools.ALL_TOOLS
        if tool["writes"] and "destructive" not in tool
    ]

    assert undeclared == []


def test_cancelling_a_task_takes_the_phrase_end_to_end():
    tool, calls = _tool("update_task_status")

    memory.hold(
        PHONE,
        tool,
        {
            "task_id": "tsk_0001",
            "status": "cancelled",
        },
    )

    reply = brain._handle_pending_reply(
        _person(),
        PHONE,
        "yes",
        memory.peek_pending(PHONE),
    )

    assert len(calls) == 0
    assert "cancelled" in reply.lower()

    memory.hold(
        PHONE,
        tool,
        {
            "task_id": "tsk_0001",
            "status": "cancelled",
        },
    )

    brain._handle_pending_reply(
        _person(),
        PHONE,
        brain.CONFIRM_PHRASE,
        memory.peek_pending(PHONE),
    )

    assert len(calls) == 1


def test_sending_work_to_a_client_takes_the_phrase_end_to_end():
    tool, calls = _tool("update_task_status")

    memory.hold(
        PHONE,
        tool,
        {
            "task_id": "tsk_0001",
            "status": "client_review",
        },
    )

    brain._handle_pending_reply(
        _person(),
        PHONE,
        "تمام",
        memory.peek_pending(PHONE),
    )

    assert len(calls) == 0


def test_moving_a_task_along_internally_still_takes_a_plain_yes():
    tool, calls = _tool("update_task_status")

    memory.hold(
        PHONE,
        tool,
        {
            "task_id": "tsk_0001",
            "status": "in_progress",
        },
    )

    brain._handle_pending_reply(
        _person(),
        PHONE,
        "yes",
        memory.peek_pending(PHONE),
    )

    assert len(calls) == 1