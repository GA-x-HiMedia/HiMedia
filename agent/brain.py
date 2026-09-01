"""Handles AI replies, tool calls, confirmations, and status updates."""

from __future__ import annotations

import json
from typing import Callable

from openai import OpenAI, RateLimitError

from . import audit, memory
from .config import GEMINI_API_KEY, GEMINI_BASE_URL
from .himedia import ApiRefused
from .tools import NOT_YOURS, describe, find_tool, is_destructive, may_act_on, public_part, tools_for


_ai_client: OpenAI | None = None

MODEL = "gemini-3.6-flash"
MAX_ROUNDS = 6  # Prevent unlimited tool-call loops.


AFFIRMATIVE = {
    "yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "confirmed",
    "اي", "أي", "ايوه", "أيوه", "نعم", "اكيد", "أكيد", "تمام", "اوك", "أوك",
}


NEGATIVE = {
    "no", "n", "nope", "cancel",
    "لا", "كنسل", "الغاء", "إلغاء",
}


# Destructive actions require an exact confirmation phrase.
CONFIRM_PHRASE = "تأكيد نهائي"


def needs_exact_phrase(tool_name: str, args: dict) -> bool:
    """Checks whether an action needs exact confirmation."""
    return is_destructive(tool_name, args)


def _client() -> OpenAI:
    """Creates the AI client when first needed."""
    global _ai_client

    if _ai_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is empty. Check .env in the project root has "
                "GEMINI_API_KEY=<your key>, and that no empty GEMINI_API_KEY "
                "is already exported in this shell."
            )

        _ai_client = OpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL)

    return _ai_client


def _system_prompt(person: dict, language: str) -> str:
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
        f"{company}. {voice} "
        f"Reply ONLY in {'Arabic' if language == 'ar' else 'English'} for this message. "
        "People switch languages mid-conversation, so detect the language per message. "
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


def _quota_message(language: str) -> str:
    """Returns a message when the API usage limit is reached."""
    if language == "ar":
        return "الخدمة وصلت الحد اليومي مؤقتًا. جرّب بعد شوي أو كلّم فريق الدعم."
    return "The assistant has hit its daily usage limit for now. Please try again later."


def _emit(on_status: Callable[[str], None] | None, text: str) -> None:
    """Sends a status update when a callback is available."""
    if on_status is not None:
        on_status(text)


def _language_of(message: str) -> str:
    """Detects whether a message contains Arabic text."""
    return "ar" if any("\u0600" <= ch <= "\u06ff" for ch in message) else "en"


def reply_to(person: dict, message: str, phone: str, on_status: Callable[[str], None] | None = None) -> str:
    turn = audit.Timer()
    turn.__enter__()

    # Detect the language from the current message.
    language = _language_of(message)

    def _finish(reply: str, rounds: int) -> str:
        turn.__exit__()

        audit.log_stage(
            phone=phone,
            stage="rounds_used",
            duration_ms=0.0,
            detail=f"{rounds} of {MAX_ROUNDS} ({language})",
        )

        audit.log_stage(
            phone=phone,
            stage="total",
            duration_ms=turn.elapsed_ms,
            detail=language,
        )

        return reply

    pending = memory.peek_pending(phone)

    if pending is not None:
        return _finish(_handle_pending_reply(person, phone, message, pending), 0)

    tools = tools_for(person)
    by_name = {t["function"]["name"]: t for t in tools}

    messages = [{"role": "system", "content": _system_prompt(person, language)}]
    messages += memory.history_for(phone)
    messages.append({"role": "user", "content": message})

    for round_number in range(1, MAX_ROUNDS + 1):
        _emit(on_status, "Thinking…")

        try:
            with audit.Timer() as model_round:
                answer = _client().chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=[public_part(t) for t in tools],
                ).choices[0].message

            audit.log_stage(
                phone=phone,
                stage=f"model_round_{round_number}",
                duration_ms=model_round.elapsed_ms,
                detail=language,
            )

        except RateLimitError:
            _log(person, phone, "gemini.chat.completions", {}, "rate_limited", 0.0, False)
            return _finish(_quota_message(language), round_number)

        messages.append(answer)

        if not answer.tool_calls:
            memory.remember(phone, "user", message)
            memory.remember(phone, "assistant", answer.content)
            return _finish(answer.content or "", round_number)

        for call in answer.tool_calls:
            tool = by_name.get(call.function.name)

            _emit(on_status, f"Calling {call.function.name}…")

            if tool is None:
                bad_args = json.loads(call.function.arguments or "{}")
                out = {"error": "That tool is not available to you."}
                _log(person, phone, call.function.name, bad_args, out, 0.0, False)

            elif tool["writes"]:
                args = json.loads(call.function.arguments or "{}")

                if not may_act_on(person, args):
                    out = NOT_YOURS
                    _log(person, phone, tool["function"]["name"], args, out, 0.0, False)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(out, ensure_ascii=False),
                    })
                    continue

                memory.hold(phone, tool, args)
                memory.remember(phone, "user", message)

                preview = describe(tool["function"]["name"], args)

                _log(
                    person,
                    phone,
                    tool["function"]["name"],
                    args,
                    "held for confirmation",
                    0.0,
                    True,
                )

                # Ask for confirmation in the same language as the current message.
                if needs_exact_phrase(tool["function"]["name"], args):
                    if language == "ar":
                        ask = f"{preview}.\nللتأكيد اكتب «{CONFIRM_PHRASE}» بالضبط."
                    else:
                        ask = f"{preview}.\nTo confirm, reply with exactly: {CONFIRM_PHRASE}"
                else:
                    if language == "ar":
                        ask = f"{preview}. تأكيد؟"
                    else:
                        ask = f"{preview}. Confirm?"

                return _finish(ask, round_number)

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

                audit.log_stage(
                    phone=phone,
                    stage=f"tool:{tool['function']['name']}",
                    duration_ms=t.elapsed_ms,
                    detail=language,
                )

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(out, ensure_ascii=False),
            })

    if language == "ar":
        final_message = "ما قدرت أكمل الطلب. جرّب تسألني بطريقة ثانية."
    else:
        final_message = "I couldn't complete the request. Please try asking in a different way."

    return _finish(final_message, MAX_ROUNDS)


_PHRASE_CANCELLED_AR = (
    "ألغيت الطلب. هذا إجراء نهائي، وما ينفّذ إلا إذا كتبت "
    "«{phrase}» بالضبط. اطلبه مرة ثانية إذا تبيه."
)

_PHRASE_CANCELLED_EN = (
    "Cancelled. That one is final, so it only runs if you reply "
    "with exactly “{phrase}”. Ask again if you still want it."
)


def _handle_pending_reply(person: dict, phone: str, message: str, pending: dict) -> str:
    # Detect the language from the current confirmation message.
    stripped = message.strip().lower()
    language = _language_of(message)

    if needs_exact_phrase(pending["tool"]["function"]["name"], pending["args"]):
        if message.strip() != CONFIRM_PHRASE:
            held = memory.pop_pending(phone)

            _log(
                person,
                phone,
                held["tool"]["function"]["name"],
                held["args"],
                "cancelled: confirmation phrase not given",
                0.0,
                False,
            )

            template = _PHRASE_CANCELLED_AR if language == "ar" else _PHRASE_CANCELLED_EN
            reply = template.format(phrase=CONFIRM_PHRASE)

            memory.remember(phone, "user", message)
            memory.remember(phone, "assistant", reply)

            return reply

        # Continue through the normal confirmation flow.
        stripped = "yes"

    if stripped in AFFIRMATIVE:
        held = memory.pop_pending(phone)
        tool = held["tool"]
        args = held["args"]

        # Re-check permissions before executing the action.
        if find_tool(tool["function"]["name"], tools_for(person)) is None:
            if language == "ar":
                reply = "ما عندك صلاحية لهذا الإجراء الحين."
            else:
                reply = "You no longer have permission for that action."

            _log(person, phone, tool["function"]["name"], args, reply, 0.0, False)
            memory.remember(phone, "user", message)
            memory.remember(phone, "assistant", reply)

            return reply

        with audit.Timer() as t:
            try:
                tool["run"](person, args)
                ok = True

                if language == "ar":
                    reply = f"تم. {describe(tool['function']['name'], args)}"
                else:
                    reply = f"Done. {describe(tool['function']['name'], args)}"

            except ApiRefused as e:
                ok = False

                if language == "ar":
                    reply = f"تعذّر: {e.message}"
                else:
                    reply = f"Could not do that: {e.message}"

        _log(person, phone, tool["function"]["name"], args, reply, t.elapsed_ms, ok)

        memory.remember(phone, "user", message)
        memory.remember(phone, "assistant", reply)

        return reply

    if stripped in NEGATIVE:
        held = memory.pop_pending(phone)

        _log(
            person,
            phone,
            held["tool"]["function"]["name"],
            held["args"],
            "cancelled by user",
            0.0,
            False,
        )

        if language == "ar":
            reply = "تم الإلغاء."
        else:
            reply = "Cancelled."

        memory.remember(phone, "user", message)
        memory.remember(phone, "assistant", reply)

        return reply

    # Keep the action pending until the user clearly confirms or cancels.
    tool = pending["tool"]
    args = pending["args"]
    preview = describe(tool["function"]["name"], args)

    if language == "ar":
        return f"عندك طلب معلّق: {preview}. أكّد بكتابة «أي» أو ألغِه بكتابة «لا»."

    return f"You still have a pending action: {preview}. Reply 'yes' to confirm or 'no' to cancel."