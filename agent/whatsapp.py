"""Handles WhatsApp messages and sends agent responses."""

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
    """Verifies the WhatsApp webhook."""
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
        # Ignore delivery updates and non-message events.
        return {"ok": True}

    if msg.get("type") != "text":
        # Ignore unsupported message types.
        return {"ok": True}

    sender = msg["from"]
    text = msg["text"]["body"]

    # Process the message in the background.
    bg.add_task(think_and_send, sender, text)

    return {"ok": True}


def send_whatsapp(to: str, text: str) -> None:
    """Sends a text message through the WhatsApp API."""
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
    """Identifies the user, processes the message, and sends a reply."""
    try:
        person = identity.who_is(sender)

        # Check the user's device before processing the request.
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