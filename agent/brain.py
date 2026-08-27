"""
The agent loop. Takes a message and a person, returns a reply.

Confirmation flow: when the model requests a write tool, it is not run —
it's stashed via memory.hold() and a one-line preview is returned instead,
ending the turn. The next message either confirms (runs the held action),
declines (discards it), or if it's neither, reminds the person what's
still pending.

Every tool call, read or write, confirmed or refused, is logged via
audit.log_tool_call.

Status indicator: reply_to() takes an optional on_status callback that
fires "Thinking…" before each model round and "Calling <tool_name>…"
before each tool call/hold. Callers that don't pass one (tests, demo.py)
are unaffected — _emit() is a no-op without a listener.

Gemini is used here as a temporary replacement, reached through Google's
OpenAI-compatible endpoint — this keeps the `openai` Python library and
the tool-calling code below unchanged.
"""
from __future__ import annotations

import json
from typing import Callable

from openai import OpenAI, RateLimitError

from . import audit, memory
from .config import GEMINI_API_KEY, GEMINI_BASE_URL
from .himedia import ApiRefused
from .tools import describe, public_part, tools_for

_ai_client: OpenAI | None = None
MODEL = "gemini-3.6-flash"
MAX_ROUNDS = 6  # a hard stop — never let this run free

AFFIRMATIVE = {
    "yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "confirmed",
    "اي", "أي", "ايوه", "أيوه", "نعم", "اكيد", "أكيد", "تمام", "اوك", "أوك",
}
NEGATIVE = {
    "no", "n", "nope", "cancel",
    "لا", "كنسل", "الغاء", "إلغاء",
}


def _client() -> OpenAI:
    """Created lazily so importing this module doesn't require an API key
    to already be set — only actually talking to the model does."""
    global _ai_client
    if _ai_client is None:
        if not GEMINI_API_KEY:
            # Without this check, an empty key silently produces
            # "Authorization: Bearer " and fails deep inside httpcore
            # with an opaque LocalProtocolError. Catch it here instead.
            raise RuntimeError(
                "GEMINI_API_KEY is empty. Check .env in the project root has "
                "GEMINI_API_KEY=<your key>, and that no empty GEMINI_API_KEY "
                "is already exported in this shell."
            )
        _ai_client = OpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL)
    return _ai_client


def _system_prompt(person: dict) -> str:
    name = person["user"]["full_name"]
    role = person["role"].get("name") or person["role"]["key"]
    company = person["company"]["name"]

    if person["audience"] == "client":
        voice = (
            "You speak to a CLIENT contact. Be calm and focused on deliverables. Never "
            "mention internal drafts, staff names, costs, invoices, or another client's "
            "work — if a tool result doesn't include something, that is not an accident, "
            "do not speculate about it."
        )
    else:
        voice = (
            "You speak to media-company staff. Be direct and practical. Use production "
            "language: versions, cuts, deadlines."
        )

    return (
        f"You are the HiMedia WhatsApp agent. You are talking to {name}, {role} at "
        f"{company}. {voice} Reply in the same language the person just used (Arabic or "
        "English) — people switch languages mid-conversation, detect it per message. "
        "When replying in Arabic, use natural, clear Bahraini Arabic with a professional "
        "and conversational tone. Use Bahraini dialect naturally where appropriate, but "
        "do not overuse slang or force dialect. Keep technical and production terms clear "
        "and accurate. Language and tone must never override audience restrictions or "
        "permissions. "
        "Keep IDs, numbers, and dates in Latin digits regardless of language. Never "
        "invent a project, task, version, or number you did not get from a tool result. "
        "If a tool call is refused, tell the person plainly what happened in their "
        "language — never retry a different way to get around a refusal."
    )


def _log(person: dict, phone: str, tool_name: str, args: dict, out, duration_ms: float, ok: bool) -> None:
    audit.log_tool_call(
        phone=phone,
        name=person["user"]["full_name"],
        role=person["role"]["key"],
        tool=tool_name,
        args=args,
        result_summary=str(out),
        duration_ms=duration_ms,
        allowed=ok,
    )


def _quota_message(person: dict) -> str:
    """Gemini's free tier is capped at 20 requests/day per model — this
    fires when that's exhausted, so the person gets a plain answer
    instead of the conversation silently dying."""
    if person["user"].get("locale") == "ar":
        return "الخدمة وصلت الحد اليومي مؤقتًا. جرّب بعد شوي أو كلّم فريق الدعم."
    return "The assistant has hit its daily usage limit for now. Please try again later."


def _emit(on_status: Callable[[str], None] | None, text: str) -> None:
    """Fire the status callback if one is attached. No-op otherwise, so
    callers that don't care (tests, demo.py) pay nothing extra."""
    if on_status is not None:
        on_status(text)


def reply_to(
    person: dict,
    message: str,
    phone: str,
    on_status: Callable[[str], None] | None = None,
) -> str:
    pending = memory.peek_pending(phone)
    if pending is not None:
        return _handle_pending_reply(person, phone, message, pending)

    tools = tools_for(person)
    by_name = {t["function"]["name"]: t for t in tools}

    messages = [{"role": "system", "content": _system_prompt(person)}]
    messages += memory.history_for(phone)
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_ROUNDS):
        _emit(on_status, "Thinking…")
        try:
            answer = _client().chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=[public_part(t) for t in tools],
            ).choices[0].message
        except RateLimitError:
            # Free-tier quota exhausted — log it like any other failed
            # step, then answer plainly instead of crashing the CLI or
            # silently dropping a WhatsApp background task.
            _log(person, phone, "gemini.chat.completions", {}, "rate_limited", 0.0, False)
            return _quota_message(person)
        messages.append(answer)

        if not answer.tool_calls:
            memory.remember(phone, "user", message)
            memory.remember(phone, "assistant", answer.content)
            return answer.content or ""

        for call in answer.tool_calls:
            tool = by_name.get(call.function.name)  # must be in THIS turn's filtered list
            _emit(on_status, f"Calling {call.function.name}…")

            if tool is None:
                bad_args = json.loads(call.function.arguments or "{}")
                out = {"error": "That tool is not available to you."}
                _log(person, phone, call.function.name, bad_args, out, 0.0, False)
            elif tool["writes"]:
                # Do not run it. Hold it, describe it, and end the turn.
                args = json.loads(call.function.arguments or "{}")
                memory.hold(phone, tool, args)
                memory.remember(phone, "user", message)
                preview = describe(tool["function"]["name"], args)
                _log(person, phone, tool["function"]["name"], args, "held for confirmation", 0.0, True)
                return f"{preview}. \u062a\u0623\u0643\u064a\u062f\u061f (confirm?)"
            else:
                args = json.loads(call.function.arguments or "{}")
                with audit.Timer() as t:
                    try:
                        out = tool["run"](person, args)
                        ok = True
                    except ApiRefused as e:
                        out = {"refused": e.code, "reason": e.message}
                        ok = False
                _log(person, phone, tool["function"]["name"], args, out, t.elapsed_ms, ok)

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(out, ensure_ascii=False),
            })

    return "\u0645\u0627 \u0642\u062f\u0631\u062a \u0623\u0643\u0645\u0644 \u0627\u0644\u0637\u0644\u0628. \u062c\u0631\u0651\u0628 \u062a\u0633\u0623\u0644 \u0628\u0637\u0631\u064a\u0642\u0629 \u062b\u0627\u0646\u064a\u0629."


def _handle_pending_reply(person: dict, phone: str, message: str, pending: dict) -> str:
    stripped = message.strip().lower()

    if stripped in AFFIRMATIVE:
        held = memory.pop_pending(phone)
        tool, args = held["tool"], held["args"]
        with audit.Timer() as t:
            try:
                tool["run"](person, args)
                ok = True
                reply = f"{'تم' if person['user'].get('locale') == 'ar' else 'Done'}. {describe(tool['function']['name'], args)}"
            except ApiRefused as e:
                ok = False
                reply = f"{'تعذّر' if person['user'].get('locale') == 'ar' else 'Could not do that'}: {e.message}"
        _log(person, phone, tool["function"]["name"], args, reply, t.elapsed_ms, ok)
        memory.remember(phone, "user", message)
        memory.remember(phone, "assistant", reply)
        return reply

    if stripped in NEGATIVE:
        held = memory.pop_pending(phone)
        _log(person, phone, held["tool"]["function"]["name"], held["args"], "cancelled by user", 0.0, False)
        reply = "تم الإلغاء." if person["user"].get("locale") == "ar" else "Cancelled."
        memory.remember(phone, "user", message)
        memory.remember(phone, "assistant", reply)
        return reply

    # Neither a clear yes nor no — remind them, don't silently drop or run it.
    tool, args = pending["tool"], pending["args"]
    preview = describe(tool["function"]["name"], args)
    if person["user"].get("locale") == "ar":
        return f"لسا عندك طلب معلّق: {preview}. أكّد بكتابة «أي» أو الغِ بكتابة «لا»."
    return f"You still have a pending action: {preview}. Reply 'yes' to confirm or 'no' to cancel."