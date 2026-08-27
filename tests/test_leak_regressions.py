"""
One regression test per leak found in the Step 3 audit.

A leak here means: a client caller can see, or cause us to send out,
information meant only for staff — staff names, vendor names, costs, drafts,
version labels, invoice numbers, or `client_visible: false` internal comments.

Every test in this file is pure logic. The sandbox is replaced with a small
fake seeded to match the shape of the real one, so these run with plain
`pytest`, with no network and no model key. That matters: the live leak test
needs both, and a leak test you cannot run is a leak test nobody runs.

The fake deliberately hands back MORE than the caller should see — internal
tasks, the other client's version, staff names, an internal comment. If a
filter is missing, the forbidden value reaches the caller and the test fails.
That is the point: we are testing our filtering, not the sandbox's.
"""
import pytest

from agent import brain, himedia, memory, tools

# --- the fake sandbox -------------------------------------------------------

FATIMA_PHONE = "+97333000020"   # client_approver @ Bank of Salam
KHALID_PHONE = "+97333000003"   # editor @ Hussain Media (internal)

SALAM_TASK = "tsk_salam"        # shared with the client
INTERNAL_TASK = "tsk_internal"  # Hussain Media's own, never hers
SALAM_VERSION = "ver_reels_v2"  # published to her
BATELCO_VERSION = "ver_teaser_v1"  # the OTHER client's work

# What each phone number is allowed to see, as the list endpoints would answer.
# Note the assignee_name on the CLIENT's own row: that is what the real
# sandbox returns. `?phone=` filters which rows come back, not which fields,
# so the staff name rides along on a task the client is entitled to see.
_VISIBLE_TASKS = {
    FATIMA_PHONE: [{"id": SALAM_TASK, "title": "Ramadan reels", "status": "client_review",
                    "priority": "normal", "due_on": "2026-03-01", "project_name": "Ramadan",
                    "assignee_id": "usr_khalid", "assignee_name": "Khalid Al-Dossary"}],
    KHALID_PHONE: [
        {"id": SALAM_TASK, "title": "Ramadan reels", "status": "client_review",
         "priority": "normal", "due_on": "2026-03-01", "project_name": "Ramadan",
         "assignee_id": "usr_khalid", "assignee_name": "Khalid Al-Dossary"},
        {"id": INTERNAL_TASK, "title": "Batelco 5G hero film grade", "status": "in_progress",
         "priority": "urgent", "due_on": "2026-02-20", "project_name": "Batelco 5G",
         "assignee_id": "usr_khalid", "assignee_name": "Khalid Al-Dossary"},
    ],
}

_VISIBLE_VERSIONS = {
    FATIMA_PHONE: [{"id": SALAM_VERSION, "version_no": 2, "state": "client_review",
                    "published_to_client": True, "deliverable_name": "Ramadan reels"}],
    KHALID_PHONE: [
        {"id": SALAM_VERSION, "version_no": 2, "state": "client_review",
         "published_to_client": True, "deliverable_name": "Ramadan reels"},
        {"id": BATELCO_VERSION, "version_no": 3, "state": "draft",
         "published_to_client": False, "deliverable_name": "Batelco 5G teaser"},
    ],
}

# Comments on the SHARED task: one client-safe, one internal-only.
_TASK_COMMENTS = {
    SALAM_TASK: [
        {"body": "Sent over for your review.", "author_name": "Khalid Al-Dossary",
         "author_kind": "staff", "client_visible": True, "created_at": "2026-02-10T09:00:00Z"},
        {"body": "Batelco invoice 1,400 BHD still unpaid, chase before we grade this.",
         "author_name": "Khalid Al-Dossary", "author_kind": "staff",
         "client_visible": False, "created_at": "2026-02-11T09:00:00Z"},
    ],
}

_VERSION_COMMENTS = {
    SALAM_VERSION: [
        {"body": "Logo needs another second.", "author_name": "Fatima Al-Kooheji",
         "author_kind": "client", "timecode_seconds": 28, "resolved": False},
        {"body": "Regrade before Manara sees the cut.", "author_name": "Khalid Al-Dossary",
         "author_kind": "staff", "timecode_seconds": 12, "resolved": False,
         "client_visible": False},
    ],
}

# Anything a client must never see in a tool result.
FORBIDDEN_FOR_A_CLIENT = [
    "khalid", "al-dossary",          # staff names
    "batelco", "5g",                 # the other client
    "invoice", "1,400", "bhd",       # money
    "draft", "hero film",            # internal work
]


def _leaked(payload) -> list[str]:
    text = str(payload).lower()
    return [word for word in FORBIDDEN_FOR_A_CLIENT if word in text]


class _Recorder(dict):
    """Records the writes the fake sandbox was asked to perform."""


@pytest.fixture
def sandbox(monkeypatch):
    """Replace every himedia endpoint tools.py touches."""
    calls = _Recorder(writes=[], task_comment_kwargs=[])

    def list_tasks(phone=None, status=None, project_id=None, open_only=None, limit=None):
        return {"data": list(_VISIBLE_TASKS.get(phone, [])), "total": 0}

    def list_versions(phone=None, project_id=None, deliverable_id=None, state=None):
        rows = list(_VISIBLE_VERSIONS.get(phone, []))
        if state is not None:
            rows = [r for r in rows if r["state"] == state]
        return rows

    def get_task(task_id):
        for rows in _VISIBLE_TASKS.values():
            for row in rows:
                if row["id"] == task_id:
                    return row
        raise AssertionError("get_task called for an unknown id: " + task_id)

    def list_task_comments(task_id, client_visible_only=False):
        calls["task_comment_kwargs"].append((task_id, client_visible_only))
        rows = _TASK_COMMENTS.get(task_id, [])
        if client_visible_only:
            rows = [r for r in rows if r.get("client_visible")]
        return list(rows)

    def list_version_comments(version_id, unresolved_only=False):
        return list(_VERSION_COMMENTS.get(version_id, []))

    def update_task(task_id, changes):
        calls["writes"].append(("update_task", task_id))
        return {"id": task_id, "title": "x", "status": changes.get("status")}

    def add_task_comment(task_id, body, author_phone, client_visible=False):
        calls["writes"].append(("add_task_comment", task_id))
        return {"id": "cmt_1"}

    def add_version_comment(version_id, body, author_phone, timecode_seconds=None):
        calls["writes"].append(("add_version_comment", version_id))
        return {"id": "cmt_1", "timecode_seconds": timecode_seconds}

    def decide_version(version_id, decision, actor_phone, note=None):
        calls["writes"].append(("decide_version", version_id))
        return {"version": {"state": "approved"}}

    def list_projects(phone=None, status=None):
        return []

    for name, fn in [
        ("list_tasks", list_tasks), ("list_versions", list_versions),
        ("get_task", get_task), ("list_task_comments", list_task_comments),
        ("list_version_comments", list_version_comments), ("update_task", update_task),
        ("add_task_comment", add_task_comment), ("add_version_comment", add_version_comment),
        ("decide_version", decide_version), ("list_projects", list_projects),
    ]:
        monkeypatch.setattr(himedia, name, fn)

    return calls


def _client():
    return {
        "user": {"full_name": "Fatima Al-Kooheji", "phone": FATIMA_PHONE, "locale": "en"},
        "company": {"id": "cmp_salam", "name": "Bank of Salam", "kind": "client"},
        "role": {"key": "client_approver", "name": "client_approver"},
        "audience": "client",
        "permissions": {"projects": "read", "reviews": "write", "tasks": "read"},
        "counts": {},
    }


def _staff():
    return {
        "user": {"full_name": "Khalid Al-Dossary", "phone": KHALID_PHONE, "locale": "en"},
        "company": {"id": "cmp_hussain", "name": "Hussain Media", "kind": "media_company"},
        "role": {"key": "editor", "name": "editor"},
        "audience": "internal",
        "permissions": {"tasks": "write", "reviews": "write", "projects": "read"},
        "counts": {},
    }


# --- leak 1 -----------------------------------------------------------------


def test_leak_review_notes_on_another_clients_version(sandbox):
    """get_review_notes acted on any version id it was handed, with no caller
    phone and no visibility check — so naming the other client's version id
    returned its notes."""
    out = tools.run_get_review_notes(_client(), {"version_id": BATELCO_VERSION})

    assert out == tools.NOT_YOURS
    assert _leaked(out) == []


# --- leak 2 -----------------------------------------------------------------


def test_leak_staff_name_in_review_note_author(sandbox):
    """Even on a version she may see, notes came back with author_name — the
    editor's real name — which a client must never be shown."""
    out = tools.run_get_review_notes(_client(), {"version_id": SALAM_VERSION})

    assert _leaked(out) == [], out
    assert all(note["author"] in ("your team", "the production team") for note in out)

    # Staff still get the real name; the filter is about audience, not secrecy.
    staff_out = tools.run_get_review_notes(_staff(), {"version_id": SALAM_VERSION})
    assert any(n["author"] == "Khalid Al-Dossary" for n in staff_out)


# --- leak 3 -----------------------------------------------------------------


def test_leak_internal_comment_on_a_version(sandbox):
    """A version note flagged client_visible:false was returned to a client
    along with the rest."""
    out = tools.run_get_review_notes(_client(), {"version_id": SALAM_VERSION})

    bodies = " ".join(n["body"] for n in out).lower()
    assert "manara" not in bodies
    assert "regrade" not in bodies


# --- leak 4 -----------------------------------------------------------------


def test_leak_published_to_client_flag_shown_to_a_client(sandbox):
    """list_versions handed the client our internal publication bookkeeping."""
    out = tools.run_list_versions(_client(), {})

    assert out and all("published_to_client" not in row for row in out)
    # Staff keep it — it is how they know whether the client is waiting.
    assert all("published_to_client" in row for row in tools.run_list_versions(_staff(), {}))


# --- leak 5 -----------------------------------------------------------------


def test_leak_internal_task_comment_reaches_a_client(sandbox):
    """The task-comment endpoint returns client_visible:false rows unless we
    ask it not to. QUESTIONS.md: applying the audience rule is our job."""
    out = tools.run_get_task_notes(_client(), {"task_id": SALAM_TASK})

    assert _leaked(out) == [], out
    assert sandbox["task_comment_kwargs"] == [(SALAM_TASK, True)]

    # And staff, on the same task, still see the internal line.
    staff_out = tools.run_get_task_notes(_staff(), {"task_id": SALAM_TASK})
    assert "invoice" in str(staff_out).lower()
    assert sandbox["task_comment_kwargs"][-1] == (SALAM_TASK, False)


# --- leak 6 -----------------------------------------------------------------


def test_leak_task_notes_on_an_internal_task(sandbox):
    """Naming an internal task id returned its title and every staff note."""
    out = tools.run_get_task_notes(_client(), {"task_id": INTERNAL_TASK})

    assert out == tools.NOT_YOURS
    assert _leaked(out) == []


# --- leak 7 -----------------------------------------------------------------


def test_leak_cross_company_write_is_not_policed_by_the_api(sandbox):
    """Reads are filtered by ?phone=; writes are not filtered at all. Without
    our own gate a client can approve another company's version by naming it."""
    person = _client()

    assert tools.run_decide_version(
        person, {"version_id": BATELCO_VERSION, "decision": "approve"}) == tools.NOT_YOURS
    assert tools.run_comment_on_version(
        person, {"version_id": BATELCO_VERSION, "body": "hi"}) == tools.NOT_YOURS
    assert tools.run_update_task_status(
        _staff(), {"task_id": "tsk_someone_elses", "status": "done"}) == tools.NOT_YOURS
    assert tools.run_comment_on_task(
        _staff(), {"task_id": "tsk_someone_elses", "body": "hi"}) == tools.NOT_YOURS

    assert sandbox["writes"] == [], "a refused write must never reach the API"


# --- leak 8 -----------------------------------------------------------------


def test_leak_write_preview_echoes_an_invisible_row(sandbox):
    """The preview is itself an answer. Confirming "Approve version
    ver_teaser_v1?" tells a client that id exists, even if the write is
    refused after they say yes."""
    person = _client()
    assert tools.may_act_on(person, {"version_id": BATELCO_VERSION}) is False
    assert tools.may_act_on(person, {"task_id": INTERNAL_TASK}) is False
    assert tools.may_act_on(person, {"version_id": SALAM_VERSION}) is True
    # No id named at all — nothing to gate, the tool filter already applied.
    assert tools.may_act_on(person, {}) is True


# --- leak 9 -----------------------------------------------------------------


def test_leak_held_write_runs_after_permission_is_lost(sandbox):
    """A write parked for confirmation ran on "yes" without re-checking.
    Permissions are re-read every 60s precisely so a demotion takes effect."""
    memory._history.clear()
    memory._pending.clear()

    person = _staff()
    tool = next(t for t in tools.ALL_TOOLS if t["function"]["name"] == "update_task_status")
    memory.hold(KHALID_PHONE, tool, {"task_id": SALAM_TASK, "status": "done"})

    person["permissions"] = {"tasks": "read"}  # demoted while it sat waiting

    reply = brain._handle_pending_reply(
        person, KHALID_PHONE, "yes", memory.peek_pending(KHALID_PHONE))

    assert "no longer have permission" in reply.lower()
    assert sandbox["writes"] == []
    assert not memory.has_pending(KHALID_PHONE)


# --- leak 10 ----------------------------------------------------------------


def test_leak_stale_held_write_still_runs(sandbox):
    """A held write waited forever, so a "yes" arriving the next morning ran
    an action the person had long forgotten agreeing to."""
    memory._history.clear()
    memory._pending.clear()

    tool = next(t for t in tools.ALL_TOOLS if t["function"]["name"] == "update_task_status")
    memory.hold(KHALID_PHONE, tool, {"task_id": SALAM_TASK, "status": "done"})
    assert memory.has_pending(KHALID_PHONE)

    memory._pending[KHALID_PHONE]["at"] -= memory.PENDING_SECONDS + 1

    assert memory.peek_pending(KHALID_PHONE) is None
    assert not memory.has_pending(KHALID_PHONE)
    assert sandbox["writes"] == []


# --- the model never chooses whose data is read -----------------------------


def test_leak_caller_phone_can_be_overridden_by_tool_arguments(sandbox):
    """Every handler takes the phone from `person`, never from `args`. If it
    ever read args, a client could pass someone else's number."""
    person = _client()
    hers = tools.run_list_tasks(person, {"open_only": False})

    for forged in ({"phone": KHALID_PHONE}, {"assignee_id": "usr_khalid"},
                   {"company_id": "cmp_hussain"}, {"audience": "internal"}):
        assert tools.run_list_tasks(person, {"open_only": False, **forged}) == hers

    assert _leaked(hers) == []


# --- leak 11 ----------------------------------------------------------------


def test_leak_staff_assignee_name_on_the_clients_own_task(sandbox):
    """`?phone=` filters which ROWS a client gets, not which FIELDS.

    Confirmed against the live sandbox: GET /v1/tasks?phone=<Fatima> returns
    her two tasks with `assignee_name: "Khalid Mansoor"` and
    `"Noor Habib"` attached. The row is legitimately hers; the staff name on it
    is not (handbook Ch. 30 — "who edits our videos?" must yield no staff
    names). Row-level filtering by the API does not imply field-level safety,
    so the tool picks its fields explicitly rather than passing the row on.
    """
    rows = tools.run_list_tasks(_client(), {"open_only": False})

    assert rows, "the client should still get her own tasks"
    for row in rows:
        assert "assignee_name" not in row
        assert "assignee_id" not in row
        assert "khalid" not in str(row).lower()

    # Staff asking the same question is unaffected — they may see who is on it.
    assert tools.run_list_tasks(_staff(), {"open_only": False})
