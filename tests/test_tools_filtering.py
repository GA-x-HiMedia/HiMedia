"""
Tool-catalogue filtering tests — full catalogue including write tools
(Phase 3). Uses fabricated `person` payloads shaped exactly like GET
/v1/permissions/by-phone responses (Chapter 12). No network call.
"""
from agent.tools import ALL_TOOLS, find_tool, tools_for


def _person(role_key: str, audience: str, permissions: dict) -> dict:
    return {
        "user": {"full_name": "Test User", "phone": "+97333099999", "locale": "en"},
        "company": {"id": "cmp_test", "name": "Test Co", "kind": "media_company"},
        "role": {"key": role_key, "name": role_key, "approval_rank": None},
        "audience": audience,
        "permissions": permissions,
        "counts": {},
    }


def test_who_am_i_is_always_offered():
    someone = _person("viewer", "internal", {})
    names = {t["function"]["name"] for t in tools_for(someone)}
    assert "who_am_i" in names


def test_accountant_has_no_review_tools_but_reads_tasks_and_projects():
    """Chapter 11: accountant has read on projects/tasks, write on
    invoices/accounting/reports — no reviews access, no tasks:write."""
    accountant = _person("accountant", "internal", {
        "invoices": "write", "accounting": "write", "reports": "read",
        "projects": "read", "tasks": "read",
    })
    names = {t["function"]["name"] for t in tools_for(accountant)}
    assert "list_versions" not in names
    assert "get_review_notes" not in names
    assert "decide_version" not in names
    assert "comment_on_version" not in names
    assert "list_tasks" in names
    assert "list_projects" in names
    # read-only on tasks, so no task-mutating tools
    assert "update_task_status" not in names
    assert "comment_on_task" not in names


def test_editor_gets_full_internal_write_set():
    """Chapter 11: editor has tasks:write, reviews:write."""
    editor = _person("editor", "internal", {
        "tasks": "write", "reviews": "write", "projects": "read", "calendar": "read",
    })
    names = {t["function"]["name"] for t in tools_for(editor)}
    assert "update_task_status" in names
    assert "comment_on_task" in names
    assert "comment_on_version" in names
    assert "decide_version" in names  # offered on scope; API enforces approval_rank


def test_client_viewer_gets_no_write_tools_at_all():
    """Chapter 11: client_viewer is read-only, cannot comment or approve."""
    viewer = _person("client_viewer", "client", {"projects": "read", "reviews": "read"})
    names = {t["function"]["name"] for t in tools_for(viewer)}
    assert "decide_version" not in names
    assert "comment_on_version" not in names
    assert "list_versions" in names
    assert "list_projects" in names
    # internal-only write tools never reach a client, regardless of scope
    assert "update_task_status" not in names
    assert "comment_on_task" not in names


def test_client_approver_can_decide_and_comment_but_not_touch_internal_tools():
    """Chapter 11: client_approver has reviews:write — can approve/reject."""
    approver = _person("client_approver", "client", {
        "projects": "read", "reviews": "write", "tasks": "read",
    })
    names = {t["function"]["name"] for t in tools_for(approver)}
    assert "decide_version" in names
    assert "comment_on_version" in names
    assert "update_task_status" not in names
    assert "comment_on_task" not in names
    assert "list_tasks" in names  # client_approver DOES have tasks:read per Ch.11


def test_forged_tool_call_for_unoffered_write_tool_is_rejected():
    client = _person("client_viewer", "client", {"projects": "read", "reviews": "read"})
    available = tools_for(client)
    assert find_tool("decide_version", available) is None
    assert find_tool("update_task_status", available) is None


def test_owner_scope_unlocks_every_tool_in_the_catalogue():
    owner = _person("owner", "internal", {m: "write" for m in ["tasks", "projects", "reviews"]})
    names = {t["function"]["name"] for t in tools_for(owner)}
    assert names == {t["function"]["name"] for t in ALL_TOOLS}


def test_catalogue_has_exactly_four_write_tools():
    write_tools = {t["function"]["name"] for t in ALL_TOOLS if t["writes"]}
    assert write_tools == {
        "update_task_status", "comment_on_task", "comment_on_version", "decide_version",
    }
