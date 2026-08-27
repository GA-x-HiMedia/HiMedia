"""
Turns a WhatsApp webhook into (phone, text), calls brain, sends the answer
back. Thin — this file should not contain any conversation logic of its
own (Chapter 22, 28-29).
"""

# edited by reem: routes through identity.device_gate, so an unknown
# number is refused and a known number on a new device is challenged.
from __future__ import annotations

import logging
import httpx
from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.responses import PlainTextResponse

from . import brain, identity
from .config import WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, WHATSAPP_VERIFY_TOKEN

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/whatsapp")
def verify(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    """WhatsApp's one-time handshake before it will send anything (Ch. 28)."""
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/whatsapp")
async def incoming(request: Request, bg: BackgroundTasks):
    body = await request.json()

    try:
        value = body["entry"][0]["changes"][0]["value"]
        msg = value["messages"][0]
    except (KeyError, IndexError):
        return {"ok": True}  # a delivery receipt, not a message

    if msg.get("type") != "text":
        return {"ok": True}  # image, audio, sticker — ignore for now

    sender = msg["from"]  # e.g. "97333000003" — no plus sign
    text = msg["text"]["body"]

    # Answer WhatsApp immediately so it doesn't retry; do the real work
    # in a background task (Chapter 29 — "answer immediately, think
    # afterwards").
    bg.add_task(think_and_send, sender, text)
    return {"ok": True}


def send_whatsapp(to: str, text: str) -> None:
    response = httpx.post(
        f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        },
        timeout=15.0,
    )
    response.raise_for_status()


def think_and_send(sender: str, text: str) -> None:
    try:
        person = identity.who_is(sender)

        # An unknown number is refused here and a known number on a new device
        # is challenged here. Both answers come back from the same call, so the
        # two cases cannot drift apart. See identity.device_gate.
        gate = identity.device_gate(person, sender, text)
        if gate is not None:
            send_whatsapp(sender, gate)
            return

        reply = brain.reply_to(
            person,
            text,
            identity.tidy(sender),
        )

        send_whatsapp(sender, reply)

    except Exception:
        logger.exception(
            "Failed to process WhatsApp message from %s",
            sender,
        )
