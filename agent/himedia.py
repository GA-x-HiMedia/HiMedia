"""HiMedia API client.

Handles all communication with the HiMedia sandbox API.
"""

from __future__ import annotations

import httpx

from .config import BASE_URL, HEADERS


class ApiRefused(Exception):
    """Raised when the API refuses a request."""

    def __init__(self, code: str, message: str, message_ar: str = "") -> None:
        self.code, self.message = code, message
        self.message_en = message
        self.message_ar = message_ar
        super().__init__(f"{code}: {message}")


def call(method: str, path: str, **kwargs):
    r = httpx.request(
        method,
        f"{BASE_URL}{path}",
        headers=HEADERS,
        timeout=20.0,
        **kwargs,
    )

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
    # Remove unused filters before sending the request.
    clean = {k: v for k, v in params.items() if v is not None}
    return call("GET", path, params=clean)


def post(path: str, body: dict):
    return call("POST", path, json=body)


def patch(path: str, body: dict):
    return call("PATCH", path, json=body)


# Named API endpoints.


def get_permissions(phone: str) -> dict:
    """Returns the user's identity and permissions."""
    return get("/v1/permissions/by-phone", phone=phone)


def list_roles() -> list[dict]:
    return get("/v1/roles")["data"]


def list_users(
    company_id: str | None = None,
    role_key: str | None = None,
    audience: str | None = None,
) -> list[dict]:
    return get(
        "/v1/users",
        company_id=company_id,
        role_key=role_key,
        audience=audience,
    )["data"]


def list_companies(kind: str | None = None) -> list[dict]:
    return get("/v1/companies", kind=kind)["data"]


def list_projects(
    phone: str | None = None,
    status: str | None = None,
) -> list[dict]:
    return get("/v1/projects", phone=phone, status=status)["data"]


def list_tasks(
    phone: str | None = None,
    status: str | None = None,
    project_id: str | None = None,
    open_only: bool | None = None,
    limit: int | None = None,
) -> dict:
    """Returns tasks and related response metadata."""
    return get(
        "/v1/tasks",
        phone=phone,
        status=status,
        project_id=project_id,
        open_only=open_only,
        limit=limit,
    )


def get_task(task_id: str) -> dict:
    """Returns a task by ID.

    Caller access must be checked before using this endpoint.
    """
    return get(f"/v1/tasks/{task_id}")


def list_task_comments(
    task_id: str,
    client_visible_only: bool = False,
) -> list[dict]:
    """Returns comments for a task.

    Clients must only receive client-visible comments.
    """
    return get(
        f"/v1/tasks/{task_id}/comments",
        client_visible_only=client_visible_only,
    )["data"]


def list_versions(
    phone: str | None = None,
    project_id: str | None = None,
    deliverable_id: str | None = None,
    state: str | None = None,
) -> list[dict]:
    """Returns deliverable versions visible to the caller."""
    return get(
        "/v1/versions",
        phone=phone,
        project_id=project_id,
        deliverable_id=deliverable_id,
        state=state,
    )["data"]


def list_version_comments(
    version_id: str,
    unresolved_only: bool = False,
) -> list[dict]:
    return get(
        f"/v1/versions/{version_id}/comments",
        unresolved_only=unresolved_only,
    )["data"]


# Write operations.


def update_task(task_id: str, changes: dict) -> dict:
    return patch(f"/v1/tasks/{task_id}", changes)


def add_task_comment(
    task_id: str,
    body: str,
    author_phone: str,
    client_visible: bool = False,
) -> dict:
    return post(
        f"/v1/tasks/{task_id}/comments",
        {
            "body": body,
            "author_phone": author_phone,
            "client_visible": client_visible,
        },
    )


def add_version_comment(
    version_id: str,
    body: str,
    author_phone: str,
    timecode_seconds: int | None = None,
) -> dict:
    payload: dict = {
        "body": body,
        "author_phone": author_phone,
    }

    if timecode_seconds is not None:
        payload["timecode_seconds"] = timecode_seconds

    return post(
        f"/v1/versions/{version_id}/comments",
        payload,
    )


def decide_version(
    version_id: str,
    decision: str,
    actor_phone: str,
    note: str | None = None,
) -> dict:
    payload: dict = {
        "decision": decision,
        "actor_phone": actor_phone,
    }

    if note:
        payload["note"] = note

    return post(
        f"/v1/versions/{version_id}/decision",
        payload,
    )