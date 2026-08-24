"""
The agent loop (Chapter 27). Takes a message and a person, returns a
reply. Knows nothing about WhatsApp, which is what makes it testable from
a terminal (Chapter 29) before any webhook exists.

Confirmation flow (Phase 3): when the model requests a write tool, we do
NOT run it — we stash it in memory.hold() and return a one-line preview
instead, ending the turn. The NEXT message either confirms (runs the held
action), declines (discards it), or — if it's neither — we remind the
person what's still pending rather than silently dropping it or silently
proceeding.

Every tool call, read or write, confirmed or refused, is logged via
audit.log_tool_call (Phase 4 — "a log of every tool call").
"""
from __future__ import annotations

import json

from openai import OpenAI

from . import audit, memory
from .config import OPENAI_KEY
from .himedia import ApiRefused
from .tools import describe, public_part, tools_for

_ai_client: OpenAI | None = None
MODEL = "gpt-4.1-mini"
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
    to already be set — only actually *talking to the model* does."""
    global _ai_client
    if _ai_client is None:
        _ai_client = OpenAI(api_key=OPENAI_KEY)
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


def reply_to(person: dict, message: str, phone: str) -> str:
    pending = memory.peek_pending(phone)
    if pending is not None:
        return _handle_pending_reply(person, phone, message, pending)

    tools = tools_for(person)
    by_name = {t["function"]["name"]: t for t in tools}

    messages = [{"role": "system", "content": _system_prompt(person)}]
    messages += memory.history_for(phone)
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_ROUNDS):
        answer = _client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[public_part(t) for t in tools],
        ).choices[0].message
        messages.append(answer)

        if not answer.tool_calls:
            memory.remember(phone, "user", message)
            memory.remember(phone, "assistant", answer.content)
            return answer.content or ""

        for call in answer.tool_calls:
            tool = by_name.get(call.function.name)  # must be in THIS turn's filtered list

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
