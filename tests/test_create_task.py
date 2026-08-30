"""Creating a task (Chapters 25-26, and the Phase 3 write rules).

The API will create a task in ANY project you name — it does not check the
caller's company on a write, the same hole every other write here is gated
against. So the rule this file pins down is:

    project the caller can see     -> created
    project the caller cannot see  -> refused, and nothing is written

It also pins the two fields the endpoint accepts but this tool deliberately
does not expose. `status` and `client_visible` both reach the client the
moment the task exists, and neither belongs in a first ask.

Written by Reem. No network: the sandbox is faked.
"""
import pytest

from agent import himedia, tools

STAFF_PHONE = "+97333000003"
MINE = "prj_mine"
THEIRS = "prj_theirs"


@pytest.fixture
def sandbox(monkeypatch):
    """A fake sandbox that records what was written."""
    written = []

    def list_projects(phone=None, status=None):
        # Only ever one project for this caller. THEIRS belongs to someone else
        # and never appears, which is exactly the point.
        return [{"id": MINE, "name": "Ramadan Campaign", "status": "active"}]

    def create_task(**kwargs):
        written.append(kwargs)
        return {"id": "tsk_new", "title": kwargs["title"], "status": "todo",
                "project_name": "Ramadan Campaign"}

    monkeypatch.setattr(himedia, "list_projects", list_projects)
    monkeypatch.setattr(himedia, "create_task", create_task)
    return written


def _staff():
    return {"user": {"full_name": "Khalid Mansoor", "phone": STAFF_PHONE, "locale": "ar"},
            "company": {"id": "cmp_hussain", "name": "Hussain Media", "kind": "media"},
            "role": {"key": "editor", "name": "editor"},
            "audience": "internal",
            "permissions": {"tasks": "write", "projects": "read", "reviews": "write"},
            "counts": {}}


def _client():
    return {"user": {"full_name": "Fatima Al-Kooheji", "phone": "+97333000010", "locale": "en"},
            "company": {"id": "cmp_salam", "name": "Bank of Salam", "kind": "client"},
            "role": {"key": "client_approver", "name": "client_approver"},
            "audience": "client",
            "permissions": {"tasks": "read", "reviews": "write"},
            "counts": {}}


# --- the gate ---------------------------------------------------------------


def test_a_task_is_created_in_a_project_the_caller_can_see(sandbox):
    out = tools.run_create_task(_staff(), {"title": "Cut the teaser", "project_id": MINE})

    assert out["id"] == "tsk_new"
    assert len(sandbox) == 1
    assert sandbox[0]["project_id"] == MINE


def test_a_project_the_caller_cannot_see_is_refused_and_nothing_is_written(sandbox):
    """The load-bearing one. The API would happily create it."""
    out = tools.run_create_task(_staff(), {"title": "Cut the teaser", "project_id": THEIRS})

    assert out == tools.NOT_YOURS
    assert sandbox == [], "a task was created in another company's project"


def test_the_refusal_does_not_confirm_the_project_exists(sandbox):
    out = tools.run_create_task(_staff(), {"title": "x", "project_id": THEIRS})

    assert THEIRS not in str(out)


# --- what the model is not allowed to set -----------------------------------


def test_client_visible_cannot_be_smuggled_through_the_arguments(sandbox):
    tools.run_create_task(_staff(), {"title": "x", "project_id": MINE,
                                     "client_visible": True})

    assert "client_visible" not in sandbox[0]


def test_status_cannot_be_smuggled_through_the_arguments(sandbox):
    """A task created straight into client_review would reach the client with
    no confirmation of any kind."""
    tools.run_create_task(_staff(), {"title": "x", "project_id": MINE,
                                     "status": "client_review"})

    assert "status" not in sandbox[0]


def test_the_schema_offered_to_the_model_forbids_both_fields():
    tool = next(t for t in tools.ALL_TOOLS if t["function"]["name"] == "create_task")
    params = tool["function"]["parameters"]

    assert params["additionalProperties"] is False
    assert "client_visible" not in params["properties"]
    assert "status" not in params["properties"]


# --- how it sits in the catalogue -------------------------------------------


def test_it_is_a_write_so_it_is_never_run_on_the_first_ask():
    tool = next(t for t in tools.ALL_TOOLS if t["function"]["name"] == "create_task")

    assert tool["writes"] is True


def test_it_is_offered_to_staff_who_can_write_tasks():
    offered = [t["function"]["name"] for t in tools.tools_for(_staff())]

    assert "create_task" in offered


def test_it_is_never_offered_to_a_client():
    offered = [t["function"]["name"] for t in tools.tools_for(_client())]

    assert "create_task" not in offered


def test_it_keeps_the_ordinary_yes_no_rather_than_the_typed_phrase():
    """It only adds internal work, and a task filed by mistake is cancelled.
    Gating it behind the phrase would be the muscle-memory problem."""
    assert tools.is_destructive("create_task", {"title": "x", "project_id": MINE}) is False


def test_the_preview_says_what_will_happen():
    preview = tools.describe("create_task", {"title": "Cut the teaser", "project_id": MINE})

    assert "Cut the teaser" in preview
    assert MINE in preview
