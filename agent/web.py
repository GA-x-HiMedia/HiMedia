"""
HTTP API for the React chat interface. Run with:

    uvicorn agent.web:app --reload --port 8000

Thin, in the same way whatsapp.py is thin (Chapter 22): it turns an HTTP
request into (phone, text), calls the same two functions the WhatsApp path
calls, in the same order, and returns what comes back. No conversation
logic, no permission logic, and no second copy of the device gate.

    person = identity.who_is(phone)
    gate   = identity.device_gate(person, phone, text)   <- unknown / new device
    reply  = brain.reply_to(person, text, phone, on_status=...)

The one thing this file adds that whatsapp.py has no use for is streaming.
brain.reply_to already reports its progress through on_status — "Thinking…",
"Calling list_tasks…" — and the CLI prints that on a line that overwrites
itself. A browser can show the same thing, so /api/chat/stream runs the turn
on a worker thread and forwards each status straight out as it happens.

Bound to localhost. There is no password on this API: it is a development
front end for a sandbox, and the moment it is exposed to a network it needs
one, because anyone who can reach it can be any of the thirteen people.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import audit, brain, himedia, identity, memory, tools
from .config import API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)

app = FastAPI(title="HiMedia agent — web")

# The Vite dev server runs on its own port, so the browser treats it as a
# different origin. Only localhost is listed: this is a dev tool.
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

# The sign-in directory lists real people. It exists so a demo can switch
# between the thirteen seeded identities without typing numbers, which is
# the whole point of the exercise - but it is still a staff directory, so it
# can be switched off with HIMEDIA_DEMO_DIRECTORY=0 and must be off anywhere
# that is not a demo.
DEMO_DIRECTORY = os.getenv("HIMEDIA_DEMO_DIRECTORY", "1") != "0"


def _require_own_device(raw_phone: str) -> str:
    """Prove this request comes from the number it claims to be.

    Naming a number is not the same as being that number. Every endpoint
    that reads or clears ONE person's data goes through here, so an employee
    cannot type a manager's number and read what they asked the agent - and
    cannot learn whether the manager uses it at all.

    The device check is the only proof of identity this project has, and it
    is already how the chat path decides who it is talking to. Reusing it
    here means there is one answer to "who are you", not two.
    """
    phone = identity.tidy(raw_phone)
    if not identity.is_trusted_device(phone):
        # Deliberately the same wording whether or not the number exists, so
        # a refusal never confirms that somebody is on the system.
        raise HTTPException(403, "This device has not been verified for that "
                                 "number. Send a message first and answer the "
                                 "verification code.")
    return phone


# --- reading a person's state ----------------------------------------------


def _person_or_404(raw_phone: str) -> tuple[dict, str]:
    """The person behind a number, and the tidy form of that number.

    A number the API does not know is a 404 here rather than a reply, because
    /api/session is the UI asking "who is this?" — not somebody talking to the
    agent. The refusal that a stranger actually sees is issued by device_gate,
    on the chat path, exactly as it is for WhatsApp.
    """
    try:
        person = identity.who_is(raw_phone)
    except himedia.ApiRefused as refused:
        raise HTTPException(502, f"{refused.code}: {refused.message}") from refused

    if person is None:
        raise HTTPException(404, identity.UNKNOWN_NUMBER_REPLY)
    return person, identity.tidy(raw_phone)


def _tool_view(person: dict) -> dict[str, Any]:
    """Which tools this person is offered, and which were taken away.

    Straight from tools_for — the same call brain.py makes on every single
    message. The UI only draws this; nothing it sends back can widen it.
    """
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
            # True for tools that ALWAYS need the phrase. The ones that decide
            # per-call (a status that cannot be undone, a comment the client
            # will see) are marked "sometimes", because that is the truth.
            "destructive": _destructive_label(tool),
            "available": available,
        }

    return {
        "tools": [one(t, t["function"]["name"] in offered_names) for t in tools.ALL_TOOLS],
        "offered": len(offered),
        "total": len(tools.ALL_TOOLS),
    }


def _destructive_label(tool: dict) -> str:
    """"no", "yes", or "sometimes" — never a guess."""
    if not tool["writes"]:
        return "no"
    verdict = tool.get("destructive", True)
    if callable(verdict):
        return "sometimes"
    return "yes" if verdict else "no"


def _pending_view(phone: str) -> dict[str, Any] | None:
    """The write waiting on a yes, described the way the person was told it.

    `describe` is the same function brain.py used to write the preview, so the
    banner in the UI and the sentence in the transcript cannot disagree.
    """
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


# --- endpoints -------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Which settings actually arrived. Says nothing secret, so it is the
    first thing to check when the UI will not talk."""
    return {
        "ok": True,
        "model": brain.MODEL,
        "model_key": bool(GEMINI_API_KEY),
        "sandbox_key": bool(API_KEY),
        "confirm_phrase": brain.CONFIRM_PHRASE,
    }


@app.get("/api/roster")
def roster() -> dict[str, Any]:
    """The thirteen seeded people, so the UI can offer a list to sign in as.

    Two API calls, not thirteen — the permission lookup for one person happens
    in /api/session when they are actually chosen.

    This is a staff directory and it is only here to make the demo
    switchable. It deliberately does NOT say whether each person has
    verified a device: that would answer "is my manager using this agent",
    which nobody is entitled to ask. Set HIMEDIA_DEMO_DIRECTORY=0 to remove
    the endpoint entirely.
    """
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
            # NOT trusted_device: whether someone has verified a device says
            # whether they use the agent, and that is nobody else's business.
        })

    people.sort(key=lambda p: (p["client_side"], p["company"], p["phone"]))
    return {"people": people}


@app.post("/api/session")
def session(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Sign in as one of them: identity, permissions, offered tools, and
    whether this device still has to prove itself."""
    raw_phone = str(payload.get("phone", "")).strip()
    if not raw_phone:
        raise HTTPException(400, "No phone number given.")

    identity.forget(raw_phone)  # never demo against a stale cache
    person, phone = _person_or_404(raw_phone)

    # Identity, role and permissions describe the account and are what the
    # sign-in screen needs before anyone has proved anything. The transcript
    # and any half-finished write are private to whoever is holding the
    # phone, so they are withheld until the device has been verified.
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
        "counts": person.get("counts", {}),
        "trusted_device": identity.is_trusted_device(phone),
        "history": memory.history_for(phone) if verified else [],
        "pending": _pending_view(phone) if verified else None,
        **_tool_view(person),
    }


def _answer(raw_phone: str, message: str,
            on_status=None) -> tuple[dict, str, str]:
    """One turn, wired exactly as whatsapp.think_and_send wires it.

    Returns (person, phone, reply). The device gate runs first and can end the
    turn on its own — an unknown number gets the flat refusal and nothing
    else, a known number on a new device gets the code challenge.
    """
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
    """One message in, one reply out. No streaming — kept because it is the
    easy thing to curl when the UI is misbehaving."""
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
    """The same turn, with brain.py's own progress forwarded as it happens.

    reply_to is synchronous and blocks for as long as the model and the tools
    take, so it runs on a worker thread and pushes each status onto a queue.
    This end drains the queue and writes one server-sent event per item —
    which is why the browser can show "Calling list_tasks…" while it is still
    happening, rather than after the reply lands.
    """
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
            # No model key. Say it plainly — this is the first thing that goes
            # wrong on a fresh clone.
            updates.put(("error", str(no_key)))
        except Exception as broke:  # a demo should explain itself
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
    """The tail of audit.log, for the panel that shows what the agent did.

    Your own entries only. `phone` used to be optional, which meant leaving
    it off returned every line for every person - each question they asked
    and each tool that ran - and passing somebody else's number returned
    theirs. It is now required and must be a number this device has proved
    it holds.

    Read, never written, and only ever the last few lines. The file is the
    record of what happened; this endpoint does not get to edit it.
    """
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
                continue  # a half-written line; the next read will have it
            # Belt and braces. `phone` is required above, so the old
            # `if phone and ...` was equivalent in practice - this just
            # cannot be re-broken by making the parameter optional again.
            if entry.get("phone") != phone:
                continue
            entries.append(entry)

    return {"entries": entries[-limit:], "path": str(path)}


@app.post("/api/reset")
def reset(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Start over. `scope` decides how far back.

    - "conversation" drops the history and any held write.
    - "device"       also makes this number verify itself again, which is the
                     only way to demo the code challenge twice in one run.
    """
    raw_phone = str(payload.get("phone", "")).strip()
    if not raw_phone:
        raise HTTPException(400, "No phone number given.")

    # Clearing somebody's transcript is acting on their data, so it needs the
    # same proof as reading it.
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
