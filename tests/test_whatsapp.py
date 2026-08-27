from fastapi.testclient import TestClient

from agent import whatsapp


client = TestClient(whatsapp.app)


def test_verify_whatsapp_success(monkeypatch):
    monkeypatch.setattr(
        whatsapp,
        "WHATSAPP_VERIFY_TOKEN",
        "test_token",
    )

    response = client.get(
        "/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_token",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.text == "12345"


def test_verify_whatsapp_wrong_token(monkeypatch):
    monkeypatch.setattr(
        whatsapp,
        "WHATSAPP_VERIFY_TOKEN",
        "correct_token",
    )

    response = client.get(
        "/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 403
    assert response.text == "forbidden"


def test_delivery_receipt_returns_ok():
    response = client.post(
        "/whatsapp",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {}
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_non_text_message_is_ignored():
    response = client.post(
        "/whatsapp",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "97333000003",
                                        "type": "image",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_text_message_is_sent_to_background_task(monkeypatch):
    calls = []

    def fake_think_and_send(sender, text):
        calls.append((sender, text))

    monkeypatch.setattr(
        whatsapp,
        "think_and_send",
        fake_think_and_send,
    )

    response = client.post(
        "/whatsapp",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "97333000003",
                                        "type": "text",
                                        "text": {
                                            "body": "شنو التاسكات؟"
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    assert calls == [
        ("97333000003", "شنو التاسكات؟")
    ]


def test_send_whatsapp_sends_correct_request(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout

        return FakeResponse()

    monkeypatch.setattr(
        whatsapp.httpx,
        "post",
        fake_post,
    )

    monkeypatch.setattr(
        whatsapp,
        "WHATSAPP_PHONE_ID",
        "123456",
    )

    monkeypatch.setattr(
        whatsapp,
        "WHATSAPP_TOKEN",
        "test_token",
    )

    whatsapp.send_whatsapp(
        "97333000003",
        "Hello",
    )

    assert "123456/messages" in captured["url"]

    assert captured["headers"] == {
        "Authorization": "Bearer test_token"
    }

    assert captured["json"]["to"] == "97333000003"
    assert captured["json"]["text"]["body"] == "Hello"


def test_unknown_user_gets_polite_message(monkeypatch):
    sent_messages = []

    monkeypatch.setattr(
        whatsapp.identity,
        "who_is",
        lambda sender: None,
    )

    monkeypatch.setattr(
        whatsapp,
        "send_whatsapp",
        lambda sender, reply: sent_messages.append(
            (sender, reply)
        ),
    )

    whatsapp.think_and_send(
        "97300000000",
        "Hello",
    )

    assert len(sent_messages) == 1

    assert sent_messages[0][0] == "97300000000"

    assert "ما لقيت رقمك" in sent_messages[0][1]