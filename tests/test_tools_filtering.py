"""
Tool catalogue filtering tests.

Checks that tools are offered based on the user's role, audience,
and permissions. It also verifies that users cannot access tools
outside their allowed permissions.

No network call is required.
"""

from agent.tools import ALL_TOOLS, find_tool, tools_for


def _person(role_key: str, audience: str, permissions: dict) -> dict:
    """Create a test user with the given role and permissions."""
    return {
        "user": {
            "full_name": "Test User",
            "phone": "+97333099999",
            "locale": "en",
        },
        "company": {
            "id": "cmp_test",
            "name": "Test Co",
            "kind": "media_company",
        },
        "role": {
            "key": role_key,
            "name": role_key,
            "approval_rank": None,
        },
        "audience": audience,
        "permissions": permissions,
        "counts": {},
    }


def test_who_am_i_is_always_offered():
    """Test that the who_am_i tool is available to every user."""
    someone = _person("viewer", "internal", {})

    names = {t["function"]["name"] for t in tools_for(someone)}

    assert "who_am_i" in names


def test_accountant_has_no_review_tools_but_reads_tasks_and_projects():
    """Test that an accountant cannot access review or task write tools."""
    accountant = _person(
        "accountant",
        "internal",
        {
            "invoices": "write",
            "accounting": "write",
            "reports": "read",
            "projects": "read",
            "tasks": "read",
        },
    )

    names = {t["function"]["name"] for t in tools_for(accountant)}

    assert "list_versions" not in names
    assert "get_review_notes" not in names
    assert "decide_version" not in names
    assert "comment_on_version" not in names

    assert "list_tasks" in names
    assert "list_projects" in names

    assert "update_task_status" not in names
    assert "comment_on_task" not in names


def test_editor_gets_full_internal_write_set():
    """Test that an editor receives the allowed internal write tools."""
    editor = _person(
        "editor",
        "internal",
        {
            "tasks": "write",
            "reviews": "write",
            "projects": "read",
            "calendar": "read",
        },
    )

    names = {t["function"]["name"] for t in tools_for(editor)}

    assert "update_task_status" in names
    assert "comment_on_task" in names
    assert "comment_on_version" in names
    assert "decide_version" in names


def test_client_viewer_gets_no_write_tools_at_all():
    """Test that a client viewer only receives read-only tools."""
    viewer = _person(
        "client_viewer",
        "client",
        {
            "projects": "read",
            "reviews": "read",
        },
    )

    names = {t["function"]["name"] for t in tools_for(viewer)}

    assert "decide_version" not in names
    assert "comment_on_version" not in names

    assert "list_versions" in names
    assert "list_projects" in names

    assert "update_task_status" not in names
    assert "comment_on_task" not in names


def test_client_approver_can_decide_and_comment_but_not_touch_internal_tools():
    """Test that a client approver can review but cannot use internal tools."""
    approver = _person(
        "client_approver",
        "client",
        {
            "projects": "read",
            "reviews": "write",
            "tasks": "read",
        },
    )

    names = {t["function"]["name"] for t in tools_for(approver)}

    assert "decide_version" in names
    assert "comment_on_version" in names

    assert "update_task_status" not in names
    assert "comment_on_task" not in names

    assert "list_tasks" in names


def test_forged_tool_call_for_unoffered_write_tool_is_rejected():
    """Test that a user cannot access tools that were not offered."""
    client = _person(
        "client_viewer",
        "client",
        {
            "projects": "read",
            "reviews": "read",
        },
    )

    available = tools_for(client)

    assert find_tool("decide_version", available) is None
    assert find_tool("update_task_status", available) is None


def test_owner_scope_unlocks_every_tool_in_the_catalogue():
    """Test that an owner with full permissions can access all tools."""
    owner = _person(
        "owner",
        "internal",
        {
            m: "write"
            for m in ["tasks", "projects", "reviews"]
        },
    )

    names = {t["function"]["name"] for t in tools_for(owner)}

    assert names == {
        t["function"]["name"]
        for t in ALL_TOOLS
    }


def test_catalogue_has_exactly_four_write_tools():
    """Test that the tool catalogue contains the expected write tools."""
    write_tools = {
        t["function"]["name"]
        for t in ALL_TOOLS
        if t["writes"]
    }

    assert write_tools == {
        "update_task_status",
        "comment_on_task",
        "comment_on_version",
        "decide_version",
    }