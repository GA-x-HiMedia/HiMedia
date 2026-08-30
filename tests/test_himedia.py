"""
HiMedia API client tests.

Checks that GET, POST, and PATCH requests send the correct parameters and
JSON bodies, successful responses are returned correctly, and expected API
errors are converted into ApiRefused exceptions.

All HTTP requests are mocked, so these tests do not need network access or
a real API key.
"""

import pytest
import httpx

from agent import himedia


def test_get_sends_clean_parameters(monkeypatch):
    """GET requests should remove parameters whose value is None."""
    captured = {}

    def fake_request(method, url, headers, timeout, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs

        request = httpx.Request(method, url)

        return httpx.Response(
            200,
            json={"ok": True},
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    result = himedia.get(
        "/v1/tasks",
        phone="+97333000003",
        status=None,
    )

    assert result == {"ok": True}
    assert captured["method"] == "GET"
    assert captured["kwargs"]["params"] == {
        "phone": "+97333000003"
    }


def test_post_sends_json_body(monkeypatch):
    """POST requests should send the supplied data as a JSON body."""
    captured = {}

    def fake_request(method, url, headers, timeout, **kwargs):
        captured["method"] = method
        captured["kwargs"] = kwargs

        request = httpx.Request(method, url)

        return httpx.Response(
            200,
            json={"ok": True},
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    body = {"status": "done"}

    result = himedia.post("/v1/tasks/tsk_0001", body)

    assert result == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["kwargs"]["json"] == body


def test_patch_sends_json_body(monkeypatch):
    """PATCH requests should send the supplied data as a JSON body."""
    captured = {}

    def fake_request(method, url, headers, timeout, **kwargs):
        captured["method"] = method
        captured["kwargs"] = kwargs

        request = httpx.Request(method, url)

        return httpx.Response(
            200,
            json={"updated": True},
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    body = {"status": "done"}

    result = himedia.patch("/v1/tasks/tsk_0001", body)

    assert result == {"updated": True}
    assert captured["method"] == "PATCH"
    assert captured["kwargs"]["json"] == body


@pytest.mark.parametrize("status_code", [400, 403, 404, 409, 422])
def test_api_errors_raise_api_refused(monkeypatch, status_code):
    """Expected API errors should be converted into ApiRefused."""

    def fake_request(method, url, headers, timeout, **kwargs):
        request = httpx.Request(method, url)

        return httpx.Response(
            status_code,
            json={
                "error": {
                    "code": "TEST_ERROR",
                    "message_en": "Test error message",
                }
            },
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    with pytest.raises(himedia.ApiRefused) as exc_info:
        himedia.get("/v1/test")

    assert exc_info.value.code == "TEST_ERROR"
    assert exc_info.value.message == "Test error message"


def test_successful_call_returns_json(monkeypatch):
    """A successful API call should return the decoded JSON response."""

    def fake_request(method, url, headers, timeout, **kwargs):
        request = httpx.Request(method, url)

        return httpx.Response(
            200,
            json={"tasks": ["task_1", "task_2"]},
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    result = himedia.call("GET", "/v1/tasks")

    assert result == {
        "tasks": ["task_1", "task_2"]
    }


def test_unexpected_http_error_is_raised(monkeypatch):
    """Unexpected server errors should remain HTTP errors."""

    def fake_request(method, url, headers, timeout, **kwargs):
        request = httpx.Request(method, url)

        return httpx.Response(
            500,
            json={"error": "Server error"},
            request=request,
        )

    monkeypatch.setattr(himedia.httpx, "request", fake_request)

    with pytest.raises(httpx.HTTPStatusError):
        himedia.get("/v1/test")