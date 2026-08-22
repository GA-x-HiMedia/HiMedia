"""
Tool-catalogue filtering tests — Phase 2 scope (read-only catalogue only).
Uses fabricated `person` payloads shaped exactly like GET
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


def test_accountant_has_no_review_tools():
    """Chapter 11: accountant has read on projects/tasks, write on
    invoices/accounting/reports — but no reviews access at all."""
    accountant = _person("accountant", "internal", {
        "invoices": "write", "accounting": "write", "reports": "read",
        "projects": "read", "tasks": "read",
    })
    names = {t["function"]["name"] for t in tools_for(accountant)}
    assert "list_versions" not in names
    assert "get_review_notes" not in names
    assert "list_tasks" in names
    assert "list_projects" in names


def test_client_viewer_gets_read_only_tools_it_has_scope_for():
    """Chapter 11: client_viewer is read-only, cannot comment or approve —
    but that distinction doesn't show up yet since Phase 2 has no write
    tools at all. What's testable now: scope still gates read access."""
    viewer = _person("client_viewer", "client", {"projects": "read", "reviews": "read"})
    names = {t["function"]["name"] for t in tools_for(viewer)}
    assert "list_versions" in names
    assert "list_projects" in names


def test_no_reviews_scope_means_no_review_tools_regardless_of_audience():
    bare_client = _person("client_viewer", "client", {"projects": "read"})
    names = {t["function"]["name"] for t in tools_for(bare_client)}
    assert "list_versions" not in names
    assert "get_review_notes" not in names


def test_forged_tool_call_for_unoffered_tool_is_rejected():
    client = _person("client_viewer", "client", {"projects": "read"})
    available = tools_for(client)
    assert find_tool("list_versions", available) is None


def test_owner_scope_unlocks_every_tool_in_the_catalogue():
    owner = _person("owner", "internal", {m: "write" for m in ["tasks", "projects", "reviews"]})
    names = {t["function"]["name"] for t in tools_for(owner)}
    assert names == {t["function"]["name"] for t in ALL_TOOLS}


def test_no_permissions_at_all_leaves_only_who_am_i():
    """If a module key is simply absent from `permissions`, it's 'none' —
    the default for anything not listed (Chapter 10)."""
    bare = _person("viewer", "internal", {})
    names = {t["function"]["name"] for t in tools_for(bare)}
    assert names == {"who_am_i"}


def test_catalogue_has_no_write_tools_yet():
    """Locks in the Phase 2 boundary: every tool in this catalogue must be
    read-only until Phase 3 explicitly adds writes + confirmation."""
    assert all(t["writes"] is False for t in ALL_TOOLS)
