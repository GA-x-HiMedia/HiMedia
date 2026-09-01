"""
HTTP API for the React chat interface.
Handles chat requests and streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import audit, brain, himedia, identity, memory, tools
from .config import API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

app = FastAPI(title="HiMedia agent — web")

# Allow local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_MESSAGE = 2000

# Demo directory for seeded users
DEMO_DIRECTORY = os.getenv("HIMEDIA_DEMO_DIRECTORY", "1") != "0"


def _require_own_device(raw_phone: str) -> str:
    """Verify that the device belongs to the number."""
    phone = identity.tidy(raw_phone)
    if not identity.is_trusted_device(phone):
        # Use the same message for unknown numbers
        raise HTTPException(403, "This device has not been verified for that "
                                 "number. Send a message first and answer the "
                                 "verification code.")
    return phone


# Read user state
def _person_or_404(raw_phone: str) -> tuple[dict, str]:
    """Get the person and cleaned phone number."""
    try:
        person = identity.who_is(raw_phone)
    except himedia.ApiRefused as refused:
        raise HTTPException(502, f"{refused.code}: {refused.message}") from refused

    if person is None:
        raise HTTPException(404, identity.UNKNOWN_NUMBER_REPLY)
    return person, identity.tidy(raw_phone)


def _tool_view(person: dict) -> dict[str, Any]:
    """Get the tools available to this person."""
    offered = tools.tools_for(person)
    offered_names = {t["function"]["name"] for t in offered}

    def one(tool: dict, available: bool) -> dict[str, Any]:
        needs = tool["needs"]
        return {
            "name": tool["function"]["name"],
            "description": (tool["function"].get("description") or "").strip(),
            "writes": bool(tool["writes"]),
            "audience": tool["audience"],
            "needs": f"{needs[0]}:{needs[1]}" if needs else None,
            # Shows if confirmation is needed
            "destructive": _destructive_label(tool),
            "available": available,
        }

    return {
        "tools": [one(t, t["function"]["name"] in offered_names) for t in tools.ALL_TOOLS],
        "offered": len(offered),
        "total": len(tools.ALL_TOOLS),
    }


def _destructive_label(tool: dict) -> str:
    """"no", "yes", or "sometimes"."""
    if not tool["writes"]:
        return "no"
    verdict = tool.get("destructive", True)
    if callable(verdict):
        return "sometimes"
    return "yes" if verdict else "no"


def _pending_view(phone: str) -> dict[str, Any] | None:
    """Get the pending action waiting for confirmation."""
    held = memory.peek_pending(phone)
    if held is None:
        return None

    name = held["tool"]["function"]["name"]
    return {
        "tool": name,
        "args": held["args"],
        "summary": tools.describe(name, held["args"]),
        "needs_phrase": brain.needs_exact_phrase(name, held["args"]),
        "phrase": brain.CONFIRM_PHRASE,
    }


# Endpoints

@app.get("/api/health")
def health() -> dict[str, Any]:
    """Check API settings."""
    return {
        "ok": True,
        "model": brain.MODEL,
        "model_key": bool(GEMINI_API_KEY),
        "sandbox_key": bool(API_KEY),
        "confirm_phrase": brain.CONFIRM_PHRASE,
    }


@app.get("/api/roster")
def roster() -> dict[str, Any]:
    """Get the demo users."""
    if not DEMO_DIRECTORY:
        raise HTTPException(404, "Not found.")

    try:
        companies = {c["id"]: c for c in himedia.list_companies()}
        users = himedia.list_users()
    except himedia.ApiRefused as refused:
        raise HTTPException(502, f"{refused.code}: {refused.message}") from refused

    people = []
    for user in users:
        company = companies.get(user.get("company_id"), {})
        people.append({
            "phone": user["phone"],
            "name": user["full_name"],
            "role": user.get("role_key", ""),
            "company": company.get("name", ""),
            "client_side": company.get("kind") == "client_org",
            # Do not expose device verification
        })

    people.sort(key=lambda p: (p["client_side"], p["company"], p["phone"]))
    return {"people": people}


@app.post("/api/session")
def session(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Return user info and available tools."""
    raw_phone = str(payload.get("phone", "")).strip()
    if not raw_phone:
        raise HTTPException(400, "No phone number given.")

    identity.forget(raw_phone)  # Clear old cache
    person, phone = _person_or_404(raw_phone)

    # Get private data only after verification
    verified = identity.is_trusted_device(phone)

    return {
        "phone": phone,
        "name": person["user"]["full_name"],
        "role": person["role"]["key"],
        "role_name": person["role"].get("name") or person["role"]["key"],
        "company": person["company"]["name"],
        "audience": person["audience"],
        "locale": person["user"].get("locale", "en"),
        "permissions": person.get("permissions", {}),
        "approval_rank": person["role"].get("approval_rank"),
        # Show workload only after verification
        "counts": person.get("counts", {}) if verified else {},
        "trusted_device": identity.is_trusted_device(phone),
        "history": memory.history_for(phone) if verified else [],
        "pending": _pending_view(phone) if verified else None,
        **_tool_view(person),
    }


def _answer(raw_phone: str, message: str,
            on_status=None) -> tuple[dict, str, str]:
    """Handle one chat message."""
    person = identity.who_is(raw_phone)
    phone = identity.tidy(raw_phone)

    gate = identity.device_gate(person, raw_phone, message)
    if gate is not None:
        return person, phone, gate

    return person, phone, brain.reply_to(person, message, phone, on_status=on_status)


def _read_request(payload: dict[str, Any]) -> tuple[str, str]:
    message = str(payload.get("message", "")).strip()[:MAX_MESSAGE]
    if not message:
        raise HTTPException(400, "Empty message.")
    raw_phone = str(payload.get("phone", "")).strip()
    if not raw_phone:
        raise HTTPException(400, "No phone number given.")
    return raw_phone, message


@app.post("/api/chat")
def chat(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Send one message and get one reply."""
    raw_phone, message = _read_request(payload)

    try:
        person, phone, reply = _answer(raw_phone, message)
    except himedia.ApiRefused as refused:
        raise HTTPException(502, f"{refused.code}: {refused.message}") from refused
    except RuntimeError as no_key:
        raise HTTPException(503, str(no_key)) from no_key

    return {
        "reply": reply,
        "pending": _pending_view(phone) if person is not None else None,
        "trusted_device": identity.is_trusted_device(phone),
    }


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(payload: dict[str, Any] = Body(default={})) -> StreamingResponse:
    """Stream chat progress to the browser."""
    raw_phone, message = _read_request(payload)
    updates: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            person, phone, reply = _answer(
                raw_phone, message,
                on_status=lambda text: updates.put(("status", text)),
            )
            updates.put(("reply", {
                "reply": reply,
                "pending": _pending_view(phone) if person is not None else None,
                "trusted_device": identity.is_trusted_device(phone),
            }))
        except himedia.ApiRefused as refused:
            updates.put(("error", f"{refused.code}: {refused.message}"))
        except RuntimeError as no_key:
            # Handle missing API key
            updates.put(("error", str(no_key)))
        except Exception as broke:  # Explain unexpected errors
            logger.exception("chat failed")
            updates.put(("error", f"{type(broke).__name__}: {broke}"))
        finally:
            updates.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def drain():
        while True:
            item = await asyncio.to_thread(updates.get)
            if item is None:
                break
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        drain(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/audit")
def audit_tail(limit: int = 60, phone: str | None = None) -> dict[str, Any]:
    """Get recent audit log entries."""
    if not phone:
        raise HTTPException(400, "A phone number is required.")
    phone = _require_own_device(phone)

    path = audit.AUDIT_LOG_PATH
    if not path.exists():
        return {"entries": [], "path": str(path)}

    limit = max(1, min(limit, 500))
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # Skip incomplete lines

            # Keep only this user's entries
            if entry.get("phone") != phone:
                continue
            entries.append(entry)

    return {"entries": entries[-limit:], "path": str(path)}


@app.post("/api/reset")
def reset(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Reset the conversation or device."""
    raw_phone = str(payload.get("phone", "")).strip()
    if not raw_phone:
        raise HTTPException(400, "No phone number given.")

    # Verify device before clearing data
    phone = _require_own_device(raw_phone)
    scope = payload.get("scope", "conversation")

    memory.pop_pending(phone)
    memory.history_for(phone).clear()

    if scope == "device":
        identity.forget_device(phone)
        identity.forget(phone)

    return {
        "ok": True,
        "scope": scope,
        "trusted_device": identity.is_trusted_device(phone),
    }


# Built interface

# Mount UI after API routes
_DIST = Path(__file__).resolve().parent.parent / "react" / "dist"

if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
else:
    logger.info("react/dist not built — API only. Run `npm run build` in react/.")