"""
Regression tests for data leaks.

Each test checks a leak that was found during the Step 3 audit.

A leak happens when a client can access staff-only information such as
staff names, other client data, costs, drafts, version details, or
internal comments.

These tests use a fake sandbox, so they run without network access or
an API key.
"""

import pytest

from agent import brain, himedia, memory, tools


# --- Fake sandbox data -------------------------------------------------------

FATIMA_PHONE = "+97333000020"  # Client user
KHALID_PHONE = "+97333000003"  # Internal user

SALAM_TASK = "tsk_salam"  # Client-visible task
INTERNAL_TASK = "tsk_internal"  # Internal task
SALAM_VERSION = "ver_reels_v2"  # Client-visible version
BATELCO_VERSION = "ver_teaser_v1"  # Another client's version


# Data returned for each user.
# Client-visible rows may still contain fields that need filtering.
_VISIBLE_TASKS = {
    FATIMA_PHONE: [
        {
            "id": SALAM_TASK,
            "title": "Ramadan reels",
            "status": "client_review",
            "priority": "normal",
            "due_on": "2026-03-01",
            "project_name": "Ramadan",
            "assignee_id": "usr_khalid",
            "assignee_name": "Khalid Al-Dossary",
        }
    ],
    KHALID_PHONE: [
        {
            "id": SALAM_TASK,
            "title": "Ramadan reels",
            "status": "client_review",
            "priority": "normal",
            "due_on": "2026-03-01",
            "project_name": "Ramadan",
            "assignee_id": "usr_khalid",
            "assignee_name": "Khalid Al-Dossary",
        },
        {
            "id": INTERNAL_TASK,
            "title": "Batelco 5G hero film grade",
            "status": "in_progress",
            "priority": "urgent",
            "due_on": "2026-02-20",
            "project_name": "Batelco 5G",
            "assignee_id": "usr_khalid",
            "assignee_name": "Khalid Al-Dossary",
        },
    ],
}


_VISIBLE_VERSIONS = {
    FATIMA_PHONE: [
        {
            "id": SALAM_VERSION,
            "version_no": 2,
            "state": "client_review",
            "published_to_client": True,
            "deliverable_name": "Ramadan reels",
        }
    ],
    KHALID_PHONE: [
        {
            "id": SALAM_VERSION,
            "version_no": 2,
            "state": "client_review",
            "published_to_client": True,
            "deliverable_name": "Ramadan reels",
        },
        {
            "id": BATELCO_VERSION,
            "version_no": 3,
            "state": "draft",
            "published_to_client": False,
            "deliverable_name": "Batelco 5G teaser",
        },
    ],
}


# Comments on the client-visible task.
_TASK_COMMENTS = {
    SALAM_TASK: [
        {
            "body": "Sent over for your review.",
            "author_name": "Khalid Al-Dossary",
            "author_kind": "staff",
            "client_visible": True,
            "created_at": "2026-02-10T09:00:00Z",
        },
        {
            "body": "Batelco invoice 1,400 BHD still unpaid, chase before we grade this.",
            "author_name": "Khalid Al-Dossary",
            "author_kind": "staff",
            "client_visible": False,
            "created_at": "2026-02-11T09:00:00Z",
        },
    ],
}


_VERSION_COMMENTS = {
    SALAM_VERSION: [
        {
            "body": "Logo needs another second.",
            "author_name": "Fatima Al-Kooheji",
            "author_kind": "client",
            "timecode_seconds": 28,
            "resolved": False,
        },
        {
            "body": "Regrade before Manara sees the cut.",
            "author_name": "Khalid Al-Dossary",
            "author_kind": "staff",
            "timecode_seconds": 12,
            "resolved": False,
            "client_visible": False,
        },
    ],
}


# Values that must not appear in client results.
FORBIDDEN_FOR_A_CLIENT = [
    "khalid",
    "al-dossary",
    "batelco",
    "5g",
    "invoice",
    "1,400",
    "bhd",
    "draft",
    "hero film",
]


def _leaked(payload) -> list[str]:
    """Returns forbidden values found in a result."""
    text = str(payload).lower()
    return [
        word
        for word in FORBIDDEN_FOR_A_CLIENT
        if word in text
    ]


class _Recorder(dict):
    """Records write calls made to the fake sandbox."""


@pytest.fixture
def sandbox(monkeypatch):
    """Replaces HiMedia API functions with fake data."""

    calls = _Recorder(
        writes=[],
        task_comment_kwargs=[],
    )

    def list_tasks(
        phone=None,
        status=None,
        project_id=None,
        open_only=None,
        limit=None,
    ):
        return {
            "data": list(_VISIBLE_TASKS.get(phone, [])),
            "total": 0,
        }

    def list_versions(
        phone=None,
        project_id=None,
        deliverable_id=None,
        state=None,
    ):
        rows = list(_VISIBLE_VERSIONS.get(phone, []))

        if state is not None:
            rows = [
                row
                for row in rows
                if row["state"] == state
            ]

        return rows

    def get_task(task_id):
        for rows in _VISIBLE_TASKS.values():
            for row in rows:
                if row["id"] == task_id:
                    return row

        raise AssertionError(
            "get_task called for an unknown id: " + task_id
        )

    def list_task_comments(
        task_id,
        client_visible_only=False,
    ):
        calls["task_comment_kwargs"].append(
            (task_id, client_visible_only)
        )

        rows = _TASK_COMMENTS.get(task_id, [])

        if client_visible_only:
            rows = [
                row
                for row in rows
                if row.get("client_visible")
            ]

        return list(rows)

    def list_version_comments(
        version_id,
        unresolved_only=False,
    ):
        return list(
            _VERSION_COMMENTS.get(version_id, [])
        )

    def update_task(task_id, changes):
        calls["writes"].append(
            ("update_task", task_id)
        )

        return {
            "id": task_id,
            "title": "x",
            "status": changes.get("status"),
        }

    def add_task_comment(
        task_id,
        body,
        author_phone,
        client_visible=False,
    ):
        calls["writes"].append(
            ("add_task_comment", task_id)
        )

        return {"id": "cmt_1"}

    def add_version_comment(
        version_id,
        body,
        author_phone,
        timecode_seconds=None,
    ):
        calls["writes"].append(
            ("add_version_comment", version_id)
        )

        return {
            "id": "cmt_1",
            "timecode_seconds": timecode_seconds,
        }

    def decide_version(
        version_id,
        decision,
        actor_phone,
        note=None,
    ):
        calls["writes"].append(
            ("decide_version", version_id)
        )

        return {
            "version": {
                "state": "approved",
            }
        }

    def list_projects(
        phone=None,
        status=None,
    ):
        return []

    for name, fn in [
        ("list_tasks", list_tasks),
        ("list_versions", list_versions),
        ("get_task", get_task),
        ("list_task_comments", list_task_comments),
        ("list_version_comments", list_version_comments),
        ("update_task", update_task),
        ("add_task_comment", add_task_comment),
        ("add_version_comment", add_version_comment),
        ("decide_version", decide_version),
        ("list_projects", list_projects),
    ]:
        monkeypatch.setattr(
            himedia,
            name,
            fn,
        )

    return calls


def _client():
    """Returns a test client user."""
    return {
        "user": {
            "full_name": "Fatima Al-Kooheji",
            "phone": FATIMA_PHONE,
            "locale": "en",
        },
        "company": {
            "id": "cmp_salam",
            "name": "Bank of Salam",
            "kind": "client",
        },
        "role": {
            "key": "client_approver",
            "name": "client_approver",
        },
        "audience": "client",
        "permissions": {
            "projects": "read",
            "reviews": "write",
            "tasks": "read",
        },
        "counts": {},
    }


def _staff():
    """Returns a test internal user."""
    return {
        "user": {
            "full_name": "Khalid Al-Dossary",
            "phone": KHALID_PHONE,
            "locale": "en",
        },
        "company": {
            "id": "cmp_hussain",
            "name": "Hussain Media",
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
            "projects": "read",
        },
        "counts": {},
    }


# --- Leak tests --------------------------------------------------------------


def test_leak_review_notes_on_another_clients_version(sandbox):
    """Checks that a client cannot access another client's version."""

    out = tools.run_get_review_notes(
        _client(),
        {"version_id": BATELCO_VERSION},
    )

    assert out == tools.NOT_YOURS
    assert _leaked(out) == []


def test_leak_staff_name_in_review_note_author(sandbox):
    """Checks that staff names are hidden from clients."""

    out = tools.run_get_review_notes(
        _client(),
        {"version_id": SALAM_VERSION},
    )

    assert _leaked(out) == [], out

    assert all(
        note["author"] in (
            "your team",
            "the production team",
        )
        for note in out
    )

    # Staff can still see the real author name.
    staff_out = tools.run_get_review_notes(
        _staff(),
        {"version_id": SALAM_VERSION},
    )

    assert any(
        note["author"] == "Khalid Al-Dossary"
        for note in staff_out
    )


def test_leak_internal_comment_on_a_version(sandbox):
    """Checks that internal version comments are hidden from clients."""

    out = tools.run_get_review_notes(
        _client(),
        {"version_id": SALAM_VERSION},
    )

    bodies = " ".join(
        note["body"]
        for note in out
    ).lower()

    assert "manara" not in bodies
    assert "regrade" not in bodies


def test_leak_published_to_client_flag_shown_to_a_client(sandbox):
    """Checks that internal version fields are hidden from clients."""

    out = tools.run_list_versions(
        _client(),
        {},
    )

    assert out and all(
        "published_to_client" not in row
        for row in out
    )

    # Staff can still see the internal field.
    assert all(
        "published_to_client" in row
        for row in tools.run_list_versions(
            _staff(),
            {},
        )
    )


def test_leak_internal_task_comment_reaches_a_client(sandbox):
    """Checks that internal task comments are filtered for clients."""

    out = tools.run_get_task_notes(
        _client(),
        {"task_id": SALAM_TASK},
    )

    assert _leaked(out) == [], out

    assert sandbox["task_comment_kwargs"] == [
        (SALAM_TASK, True)
    ]

    # Staff can still see internal comments.
    staff_out = tools.run_get_task_notes(
        _staff(),
        {"task_id": SALAM_TASK},
    )

    assert "invoice" in str(staff_out).lower()

    assert sandbox["task_comment_kwargs"][-1] == (
        SALAM_TASK,
        False,
    )


def test_leak_task_notes_on_an_internal_task(sandbox):
    """Checks that a client cannot access an internal task."""

    out = tools.run_get_task_notes(
        _client(),
        {"task_id": INTERNAL_TASK},
    )

    assert out == tools.NOT_YOURS
    assert _leaked(out) == []


def test_leak_cross_company_write_is_not_policed_by_the_api(sandbox):
    """Checks that users cannot write to data they do not own."""

    person = _client()

    assert tools.run_decide_version(
        person,
        {
            "version_id": BATELCO_VERSION,
            "decision": "approve",
        },
    ) == tools.NOT_YOURS

    assert tools.run_comment_on_version(
        person,
        {
            "version_id": BATELCO_VERSION,
            "body": "hi",
        },
    ) == tools.NOT_YOURS

    assert tools.run_update_task_status(
        _staff(),
        {
            "task_id": "tsk_someone_elses",
            "status": "done",
        },
    ) == tools.NOT_YOURS

    assert tools.run_comment_on_task(
        _staff(),
        {
            "task_id": "tsk_someone_elses",
            "body": "hi",
        },
    ) == tools.NOT_YOURS

    # Refused writes must not reach the API.
    assert sandbox["writes"] == []


def test_leak_write_preview_echoes_an_invisible_row(sandbox):
    """Checks that actions are allowed only on visible data."""

    person = _client()

    assert tools.may_act_on(
        person,
        {"version_id": BATELCO_VERSION},
    ) is False

    assert tools.may_act_on(
        person,
        {"task_id": INTERNAL_TASK},
    ) is False

    assert tools.may_act_on(
        person,
        {"version_id": SALAM_VERSION},
    ) is True

    # No resource ID means there is nothing to check.
    assert tools.may_act_on(person, {}) is True


def test_leak_held_write_runs_after_permission_is_lost(sandbox):
    """Checks that permissions are checked again before running a pending action."""

    memory._history.clear()
    memory._pending.clear()

    person = _staff()

    tool = next(
        tool
        for tool in tools.ALL_TOOLS
        if tool["function"]["name"]
        == "update_task_status"
    )

    memory.hold(
        KHALID_PHONE,
        tool,
        {
            "task_id": SALAM_TASK,
            "status": "done",
        },
    )

    # Remove write permission before confirmation.
    person["permissions"] = {
        "tasks": "read"
    }

    reply = brain._handle_pending_reply(
        person,
        KHALID_PHONE,
        "yes",
        memory.peek_pending(KHALID_PHONE),
    )

    assert "no longer have permission" in reply.lower()
    assert sandbox["writes"] == []
    assert not memory.has_pending(KHALID_PHONE)


def test_leak_stale_held_write_still_runs(sandbox):
    """Checks that expired pending actions cannot be executed."""

    memory._history.clear()
    memory._pending.clear()

    tool = next(
        tool
        for tool in tools.ALL_TOOLS
        if tool["function"]["name"]
        == "update_task_status"
    )

    memory.hold(
        KHALID_PHONE,
        tool,
        {
            "task_id": SALAM_TASK,
            "status": "done",
        },
    )

    assert memory.has_pending(KHALID_PHONE)

    # Make the pending action expire.
    memory._pending[KHALID_PHONE]["at"] -= (
        memory.PENDING_SECONDS + 1
    )

    assert memory.peek_pending(KHALID_PHONE) is None
    assert not memory.has_pending(KHALID_PHONE)
    assert sandbox["writes"] == []


# --- Caller identity ---------------------------------------------------------


def test_leak_caller_phone_can_be_overridden_by_tool_arguments(sandbox):
    """Checks that tool arguments cannot change the caller's identity."""

    person = _client()

    hers = tools.run_list_tasks(
        person,
        {"open_only": False},
    )

    for forged in (
        {"phone": KHALID_PHONE},
        {"assignee_id": "usr_khalid"},
        {"company_id": "cmp_hussain"},
        {"audience": "internal"},
    ):
        assert tools.run_list_tasks(
            person,
            {
                "open_only": False,
                **forged,
            },
        ) == hers

    assert _leaked(hers) == []


def test_leak_staff_assignee_name_on_the_clients_own_task(sandbox):
    """Checks that staff details are removed from client task data."""

    rows = tools.run_list_tasks(
        _client(),
        {"open_only": False},
    )

    assert rows, "the client should still get her own tasks"

    for row in rows:
        assert "assignee_name" not in row
        assert "assignee_id" not in row
        assert "khalid" not in str(row).lower()

    # Staff can still access their task data.
    assert tools.run_list_tasks(
        _staff(),
        {"open_only": False},
    )