"""
The only file that knows the HiMedia sandbox exists (Chapter 22). If a URL
ever needs typing anywhere else in this project, it belongs here instead.
"""
from __future__ import annotations

import httpx

from .config import BASE_URL, HEADERS


class ApiRefused(Exception):
    """The API said no. Tell the person; never work around it (Chapter 23)."""

    def __init__(self, code: str, message: str, message_ar: str = "") -> None:
        self.code, self.message = code, message
        # The sandbox returns message_ar alongside message_en. Keeping it means
        # an Arabic-speaking caller can be told why in their own language
        # instead of getting the English string back.
        self.message_en = message
        self.message_ar = message_ar
        super().__init__(f"{code}: {message}")


def call(method: str, path: str, **kwargs):
    r = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=20.0, **kwargs)
    if r.status_code in (400, 403, 404, 409, 422):
        err = r.json().get("error", {})
        raise ApiRefused(
            err.get("code", "ERROR"),
            err.get("message_en", "Something went wrong."),
            err.get("message_ar", ""),
        )
    r.raise_for_status()
    return r.json()


def get(path: str, **params):
    # Drop None values so an omitted filter doesn't get sent as the
    # literal query string "status=None".
    clean = {k: v for k, v in params.items() if v is not None}
    return call("GET", path, params=clean)


def post(path: str, body: dict):
    return call("POST", path, json=body)


def patch(path: str, body: dict):
    return call("PATCH", path, json=body)


# --- Named endpoints --------------------------------------------------------
#
# TEAM.md: "API URLs live in exactly one file: agent/himedia.py. If a URL
# needs typing anywhere else in the project, it belongs here instead — no
# exceptions." The generic get/post/patch above satisfy that only if callers
# never type a path, so every endpoint the agent uses gets a name here and
# tools.py calls the name.
#
# Restored from the earlier implementation on `reem-local-backup`, which had
# these; the shared version had drifted to typing paths inside tools.py.


def get_permissions(phone: str) -> dict:
    """Who this number belongs to, their role, and their live permissions.
    The first call made for any incoming message."""
    return get("/v1/permissions/by-phone", phone=phone)


def check_permission(phone: str, module: str, level: str = "read") -> bool:
    """Ask the API directly whether this number may do this thing."""
    return bool(get("/v1/permissions/check", phone=phone, module=module, level=level).get("allowed"))


def list_roles() -> list[dict]:
    return get("/v1/roles")["data"]


def list_users(company_id: str | None = None, role_key: str | None = None,
               audience: str | None = None) -> list[dict]:
    return get("/v1/users", company_id=company_id, role_key=role_key, audience=audience)["data"]


def list_companies(kind: str | None = None) -> list[dict]:
    return get("/v1/companies", kind=kind)["data"]


def list_projects(phone: str | None = None, status: str | None = None) -> list[dict]:
    return get("/v1/projects", phone=phone, status=status)["data"]


def list_tasks(phone: str | None = None, status: str | None = None,
               project_id: str | None = None, open_only: bool | None = None,
               limit: int | None = None) -> dict:
    """The whole envelope — {"data": [...], "total": n, "resolved_for": {...}} —
    because callers usually want the count and who it resolved to as well."""
    return get("/v1/tasks", phone=phone, status=status, project_id=project_id,
               open_only=open_only, limit=limit)


def get_task(task_id: str) -> dict:
    """By-id, and therefore NOT filtered by caller — the API trusts our key
    and hands over any task we name. Callers must gate this themselves."""
    return get(f"/v1/tasks/{task_id}")


def list_task_comments(task_id: str, client_visible_only: bool = False) -> list[dict]:
    """The conversation attached to a task.

    client_visible_only MUST be True whenever the person asking is a client.
    This endpoint takes no `phone`: it authenticates on our API key and has no
    idea who is asking, so per Chapter 19 it will hand over
    `client_visible: false` internal comments unless we say otherwise. That is
    still unconfirmed against the live sandbox (QUESTIONS.md), so we pass the
    flag on the assumption that it does NOT filter for us — the safe direction
    to be wrong in. Never call this straight from a tool; go through tools.py,
    which sets the flag from the caller's audience.
    """
    return get(f"/v1/tasks/{task_id}/comments", client_visible_only=client_visible_only)["data"]


def list_deliverables(project_id: str | None = None) -> list[dict]:
    return get("/v1/deliverables", project_id=project_id)["data"]


def list_versions(phone: str | None = None, project_id: str | None = None,
                  deliverable_id: str | None = None, state: str | None = None) -> list[dict]:
    """Versions of a deliverable. A client only ever sees published ones."""
    return get("/v1/versions", phone=phone, project_id=project_id,
               deliverable_id=deliverable_id, state=state)["data"]


def get_version(version_id: str) -> dict:
    """By-id, and therefore NOT filtered by caller — see get_task."""
    return get(f"/v1/versions/{version_id}")


def list_version_comments(version_id: str, unresolved_only: bool = False) -> list[dict]:
    return get(f"/v1/versions/{version_id}/comments", unresolved_only=unresolved_only)["data"]


# --- writes -----------------------------------------------------------------


def update_task(task_id: str, changes: dict) -> dict:
    return patch(f"/v1/tasks/{task_id}", changes)


def add_task_comment(task_id: str, body: str, author_phone: str,
                     client_visible: bool = False) -> dict:
    return post(f"/v1/tasks/{task_id}/comments",
                {"body": body, "author_phone": author_phone, "client_visible": client_visible})


def add_version_comment(version_id: str, body: str, author_phone: str,
                        timecode_seconds: int | None = None) -> dict:
    payload: dict = {"body": body, "author_phone": author_phone}
    if timecode_seconds is not None:
        payload["timecode_seconds"] = timecode_seconds
    return post(f"/v1/versions/{version_id}/comments", payload)


def decide_version(version_id: str, decision: str, actor_phone: str,
                   note: str | None = None) -> dict:
    payload: dict = {"decision": decision, "actor_phone": actor_phone}
    if note:
        payload["note"] = note
    return post(f"/v1/versions/{version_id}/decision", payload)
