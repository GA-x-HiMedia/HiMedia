from agent import memory


def setup_function(_):
    # Clean memory before every test
    memory._history.clear()
    memory._pending.clear()


def test_history_starts_empty():
    phone = "+97333000001"

    history = memory.history_for(phone)

    assert history == []


def test_remember_saves_messages():
    phone = "+97333000001"

    memory.remember(phone, "user", "Hello")
    memory.remember(phone, "assistant", "Hi!")

    history = memory.history_for(phone)

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi!"


def test_history_is_separate_for_each_phone():
    phone1 = "+97333000001"
    phone2 = "+97333000002"

    memory.remember(phone1, "user", "Message for phone 1")
    memory.remember(phone2, "user", "Message for phone 2")

    assert len(memory.history_for(phone1)) == 1
    assert len(memory.history_for(phone2)) == 1

    assert memory.history_for(phone1)[0]["content"] == "Message for phone 1"
    assert memory.history_for(phone2)[0]["content"] == "Message for phone 2"


def test_history_keeps_only_maximum_messages():
    phone = "+97333000001"

    for i in range(memory.MAX_HISTORY + 5):
        memory.remember(phone, "user", f"Message {i}")

    history = memory.history_for(phone)

    assert len(history) == memory.MAX_HISTORY
    assert history[0]["content"] == "Message 5"


def test_hold_and_peek_pending_action():
    phone = "+97333000001"

    tool = {"function": {"name": "update_task_status"}}
    args = {"task_id": "tsk_0001", "status": "done"}

    memory.hold(phone, tool, args)

    pending = memory.peek_pending(phone)

    assert pending is not None
    assert pending["tool"] == tool
    assert pending["args"] == args
    assert memory.has_pending(phone)


def test_pop_pending_removes_action():
    phone = "+97333000001"

    tool = {"function": {"name": "update_task_status"}}
    args = {"task_id": "tsk_0001", "status": "done"}

    memory.hold(phone, tool, args)

    pending = memory.pop_pending(phone)

    assert pending is not None
    assert pending["tool"] == tool
    assert pending["args"] == args
    assert not memory.has_pending(phone)
    assert memory.peek_pending(phone) is None


def test_pending_actions_are_separate_for_each_phone():
    phone1 = "+97333000001"
    phone2 = "+97333000002"

    tool1 = {"function": {"name": "update_task_status"}}
    tool2 = {"function": {"name": "comment_on_task"}}

    memory.hold(phone1, tool1, {"task_id": "tsk_0001"})
    memory.hold(phone2, tool2, {"task_id": "tsk_0002"})

    assert memory.peek_pending(phone1)["tool"] == tool1
    assert memory.peek_pending(phone2)["tool"] == tool2