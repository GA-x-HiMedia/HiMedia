"""
The only file that knows the HiMedia sandbox exists (Chapter 22). If a URL
ever needs typing anywhere else in this project, it belongs here instead.
"""
from __future__ import annotations

import httpx

from .config import BASE_URL, HEADERS


class ApiRefused(Exception):
    """The API said no. Tell the person; never work around it (Chapter 23)."""

    def __init__(self, code: str, message: str) -> None:
        self.code, self.message = code, message
        super().__init__(f"{code}: {message}")


def call(method: str, path: str, **kwargs):
    r = httpx.request(method, f"{BASE_URL}{path}", headers=HEADERS, timeout=20.0, **kwargs)
    if r.status_code in (400, 403, 404, 409, 422):
        err = r.json().get("error", {})
        raise ApiRefused(err.get("code", "ERROR"), err.get("message_en", "Something went wrong."))
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
