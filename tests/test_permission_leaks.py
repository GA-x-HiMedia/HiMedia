"""Tests for agent security fixes."""

from fastapi.testclient import TestClient

from agent import brain, identity, tools, web

client = TestClient(web.app)

MINE = "+97333000003"
SOMEONE_ELSE = "+97333000009"


def _person(rank=None, owner=False, audience="internal", perms=None):
    """Create a test person."""
    return {
        "user": {"full_name": "Test Person", "phone": MINE, "locale": "en"},
        "company": {"id": "cmp_test", "name": "Test Company"},
        "role": {"key": "editor", "approval_rank": rank, "is_owner": owner},
        "audience": audience,
        "permissions": perms if perms is not None else {"tasks": "write", "reviews": "write"},
    }


def setup_function(_):
    identity.forget_device()
    identity.forget()


def _offered(person):
    return {t["function"]["name"] for t in tools.tools_for(person)}


# Approval rank


def test_a_rank_one_editor_is_not_offered_the_approve_tool():
    """Editors cannot approve client deliverables."""
    assert "decide_version" not in _offered(_person(rank=1))


def test_a_rank_one_editor_keeps_everything_else():
    """Only remove the restricted tool."""
    offered = _offered(_person(rank=1))
    for name in ("comment_on_version", "comment_on_task", "list_tasks", "get_review_notes"):
        assert name in offered, f"{name} should still be offered to an editor"


def test_a_supervisor_and_a_director_may_still_approve():
    assert "decide_version" in _offered(_person(rank=2))
    assert "decide_version" in _offered(_person(rank=3))


def test_an_owner_may_approve_even_with_no_rank():
    """Owners can approve without a rank."""
    assert "decide_version" in _offered(_person(rank=None, owner=True))


def test_a_role_the_api_does_not_rank_is_not_blocked():
    """Unranked roles are not blocked."""
    assert "decide_version" in _offered(_person(rank=None))


def test_a_client_approver_may_still_approve_their_own_work():
    client_person = _person(rank=None, audience="client",
                            perms={"tasks": "read", "reviews": "write"})
    assert "decide_version" in _offered(client_person)


# Web API security


def test_the_audit_tail_refuses_when_no_number_is_given():
    """A phone number is required."""
    assert client.get("/api/audit").status_code == 400


def test_the_audit_tail_refuses_an_unverified_device():
    assert client.get("/api/audit", params={"phone": MINE}).status_code == 403


def test_the_audit_tail_refuses_someone_elses_number():
    """Users cannot access another person's audit log."""
    identity._verified_devices.add(identity.tidy(MINE))

    response = client.get("/api/audit", params={"phone": SOMEONE_ELSE})

    assert response.status_code == 403
    body = response.text.lower()
    assert "not exist" not in body and "unknown" not in body, (
        "the refusal must not reveal whether that number is on the system")


def test_the_audit_tail_works_for_your_own_verified_number():
    identity._verified_devices.add(identity.tidy(MINE))

    response = client.get("/api/audit", params={"phone": MINE})

    assert response.status_code == 200
    assert all(e.get("phone") == identity.tidy(MINE)
               for e in response.json()["entries"])


def test_resetting_someone_elses_conversation_is_refused():
    identity._verified_devices.add(identity.tidy(MINE))

    response = client.post("/api/reset", json={"phone": SOMEONE_ELSE})

    assert response.status_code == 403


def test_the_roster_never_says_who_has_used_the_agent(monkeypatch):
    """Do not expose device usage."""
    monkeypatch.setattr(web.himedia, "list_companies", lambda: [
        {"id": "cmp_test", "name": "Test Company", "kind": "media_company"}])
    monkeypatch.setattr(web.himedia, "list_users", lambda: [
        {"phone": MINE, "full_name": "Test Person",
         "role_key": "editor", "company_id": "cmp_test"}])
    identity._verified_devices.add(identity.tidy(MINE))

    people = client.get("/api/roster").json()["people"]

    assert people, "the roster should still list people for the demo picker"
    for entry in people:
        assert "trusted_device" not in entry


def test_the_roster_can_be_switched_off_entirely(monkeypatch):
    monkeypatch.setattr(web, "DEMO_DIRECTORY", False)

    assert client.get("/api/roster").status_code == 404


def test_a_transcript_is_withheld_until_the_device_is_verified(monkeypatch):
    """Keep private data hidden until verification."""
    monkeypatch.setattr(web.identity, "who_is", lambda raw: _person(rank=1))
    web.memory.history_for(identity.tidy(MINE)).append(
        {"role": "user", "content": "something private"})

    body = client.post("/api/session", json={"phone": MINE}).json()

    assert body["history"] == []
    assert body["pending"] is None
    assert body["name"], "identity itself is still returned, for the sign-in screen"


# Note tool descriptions


def _description(name: str) -> str:
    for tool in tools.ALL_TOOLS:
        if tool["function"]["name"] == name:
            return tool["function"]["description"].lower()
    raise AssertionError(f"no such tool: {name}")


def test_the_tool_that_writes_a_note_on_a_task_says_so():
    """The task comment tool should mention notes."""
    assert "note" in _description("comment_on_task")


def test_the_read_only_note_tools_say_they_only_read():
    for name in ("get_task_notes", "get_review_notes"):
        text = _description(name)
        assert "read" in text, f"{name} should say it reads"
        assert "comment_on" in text, f"{name} should point at the write tool"


def test_deciding_a_version_is_not_described_as_leaving_a_note():
    assert "note" not in _description("decide_version")


def test_every_write_tool_still_declares_whether_it_needs_the_phrase():
    """Every write tool must define confirmation."""
    for tool in tools.ALL_TOOLS:
        if tool["writes"]:
            assert "destructive" in tool, f"{tool['function']['name']} has not decided"
            assert isinstance(
                brain.needs_exact_phrase(tool["function"]["name"], {}), bool)