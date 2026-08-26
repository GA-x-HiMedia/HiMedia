import json
import time

from agent import audit


def test_log_tool_call_creates_json_event(tmp_path, monkeypatch):
    log_file = tmp_path / "audit.log"

    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", log_file)

    audit.log_tool_call(
        phone="+97333000003",
        name="Khalid Mansoor",
        role="editor",
        tool="list_tasks",
        args={"status": "open"},
        result_summary="Found 3 open tasks",
        duration_ms=123.456,
        allowed=True,
    )

    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1

    event = json.loads(lines[0])

    assert event["phone"] == "+97333000003"
    assert event["name"] == "Khalid Mansoor"
    assert event["role"] == "editor"
    assert event["tool"] == "list_tasks"
    assert event["args"] == {"status": "open"}
    assert event["result_summary"] == "Found 3 open tasks"
    assert event["duration_ms"] == 123.5
    assert event["allowed"] is True
    assert "ts" in event


def test_log_tool_call_appends_multiple_events(tmp_path, monkeypatch):
    log_file = tmp_path / "audit.log"

    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", log_file)

    for i in range(2):
        audit.log_tool_call(
            phone="+97333000003",
            name="Test User",
            role="editor",
            tool=f"tool_{i}",
            args={},
            result_summary="Success",
            duration_ms=10.0,
            allowed=True,
        )

    lines = log_file.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["tool"] == "tool_0"
    assert second["tool"] == "tool_1"


def test_result_summary_is_limited_to_300_characters(tmp_path, monkeypatch):
    log_file = tmp_path / "audit.log"

    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", log_file)

    long_summary = "A" * 500

    audit.log_tool_call(
        phone="+97333000003",
        name="Test User",
        role="editor",
        tool="list_tasks",
        args={},
        result_summary=long_summary,
        duration_ms=10.0,
        allowed=True,
    )

    event = json.loads(
        log_file.read_text(encoding="utf-8").splitlines()[0]
    )

    assert len(event["result_summary"]) == 300


def test_timer_measures_elapsed_time():
    with audit.Timer() as timer:
        time.sleep(0.01)

    assert timer.elapsed_ms > 0


def test_timer_elapsed_time_is_in_milliseconds():
    with audit.Timer() as timer:
        time.sleep(0.01)

    assert timer.elapsed_ms >= 5