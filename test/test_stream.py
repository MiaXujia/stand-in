from __future__ import annotations

import json

from app.core.models import DelayLimits


def _fast_delays(client) -> None:
    """测试里不要真的睡 2–8 秒。"""
    client.app.state.ctx.reply._limits = DelayLimits(
        first_ms=(0, 0),
        night_ms=(0, 0),
        gap_ms=(0, 0),
        stream_first_ms=(0, 0),
        stream_night_ms=(0, 0),
        stream_chunk_ms=0,
    )


def _events(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def test_stream_sends_parts_and_done(client) -> None:
    _fast_delays(client)
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"text": "今天好累啊", "client_msg_id": "s1"},
        headers={"X-Stand-In": "1"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = _events(body)
    assert events[0]["type"] == "start"
    assert [e["type"] for e in events].count("done") == 1
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "delta" for e in events)
    parts = [e["text"] for e in events if e["type"] == "delta"]
    assert parts, "至少要有一段文本"


def test_stream_guard_uses_fixed_reply(client) -> None:
    _fast_delays(client)
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"text": "我不想活了", "client_msg_id": "s2"},
        headers={"X-Stand-In": "1"},
    ) as response:
        body = "".join(response.iter_text())

    events = _events(body)
    assert events[0]["fixed"] is True
    assert events[-1]["type"] == "done"
    assert any("AI" in e.get("text", "") for e in events)


def test_stream_requires_session(settings) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    anon = TestClient(create_app(settings))
    response = anon.post(
        "/api/chat/stream", json={"text": "hi"}, headers={"X-Stand-In": "1"}
    )
    assert response.status_code == 401
