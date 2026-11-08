from __future__ import annotations

import httpx

HEADERS = {"X-Stand-In": "1"}


def test_call_owner_without_webhook_stays_pending(client) -> None:
    response = client.post("/api/control", json={"action": "call_owner"}, headers=HEADERS)

    assert response.status_code == 200
    assert "还没有把消息发给他" in response.json()["message"]
    assert "这就让他来找你" not in response.json()["message"]
    pending = client.app.state.ctx.inbox.unread()
    assert pending[0]["kind"] == "call-owner"
    assert pending[0]["delivery_status"] == "pending"


def test_webhook_acceptance_is_recorded_without_claiming_owner_read_it(client, monkeypatch) -> None:
    client.app.state.ctx.notifier._webhook = "https://example.invalid/notify"

    def accepted(url, **kwargs):
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", accepted)
    response = client.post("/api/control", json={"action": "call_owner"}, headers=HEADERS)

    assert response.status_code == 200
    assert "通知服务已接收" in response.json()["message"]
    assert "不能确认他看到了" in response.json()["message"]
    assert client.app.state.ctx.inbox.unread()[0]["delivery_status"] == "accepted"


def test_webhook_timeout_is_unknown_and_crisis_reply_is_truthful(client, monkeypatch) -> None:
    client.app.state.ctx.notifier._webhook = "https://example.invalid/notify"

    def timed_out(url, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "post", timed_out)
    response = client.post(
        "/api/chat",
        json={"text": "我不想活了", "client_msg_id": "crisis-timeout"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = " ".join(part["text"] for part in response.json()["parts"])
    assert "通知结果暂时无法确认" in body
    assert client.app.state.ctx.inbox.unread()[0]["delivery_status"] == "unknown"


def test_webhook_rejection_is_recorded_as_failed(client, monkeypatch) -> None:
    client.app.state.ctx.notifier._webhook = "https://example.invalid/notify"

    def rejected(url, **kwargs):
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", rejected)
    response = client.post("/api/control", json={"action": "call_owner"}, headers=HEADERS)

    assert response.status_code == 200
    assert "通知没能发出" in response.json()["message"]
    assert client.app.state.ctx.inbox.unread()[0]["delivery_status"] == "failed"
