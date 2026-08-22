"""
The agent loop — Phase 2 scope (Chapter 27). Takes a message and a
person, returns a reply. Knows nothing about WhatsApp, which is what
makes it testable from a terminal (Chapter 29) before any webhook exists.

Every tool in Phase 2's catalogue is read-only, so this loop has nothing
to confirm yet — it just runs whatever the model asks for and hands the
result back. Phase 3 adds write tools and, alongside them, a hold/confirm
step here: when a tool with `writes: True` is requested, this function
will stash it instead of running it and wait for an explicit yes on the
next message. That branch does not exist yet — don't add write tools to
tools.py without adding it back here at the same time.
"""
from __future__ import annotations

import json

from openai import OpenAI

from . import memory
from .config import OPENAI_KEY
from .himedia import ApiRefused
from .tools import public_part, tools_for

_ai_client: OpenAI | None = None
MODEL = "gpt-4.1-mini"
MAX_ROUNDS = 6  # a hard stop — never let this run free


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


def reply_to(person: dict, message: str, phone: str) -> str:
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
                out = {"error": "That tool is not available to you."}
            else:
                args = json.loads(call.function.arguments or "{}")
                try:
                    out = tool["run"](person, args)
                except ApiRefused as e:
                    out = {"refused": e.code, "reason": e.message}

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(out, ensure_ascii=False),
            })

    return "\u0645\u0627 \u0642\u062f\u0631\u062a \u0623\u0643\u0645\u0644 \u0627\u0644\u0637\u0644\u0628. \u062c\u0631\u0651\u0628 \u062a\u0633\u0623\u0644 \u0628\u0637\u0631\u064a\u0642\u0629 \u062b\u0627\u0646\u064a\u0629."
