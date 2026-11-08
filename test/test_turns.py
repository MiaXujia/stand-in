from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import pytest

from app.core.errors import LlmError, TurnConflict, TurnInProgress
from app.core.models import Completion, DelayLimits, Mode, TurnStatus
from app.main import create_app

HEADERS = {"X-Stand-In": "1"}


def test_chat_commits_an_explicit_turn_and_output_link(client) -> None:
    response = client.post(
        "/api/chat", json={"text": "今天好累", "client_msg_id": "turn-1"}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["turn_id"]
    assert body["message_id"] > 0

    status = client.get("/api/turns/by-client/turn-1").json()
    assert status["status"] == "committed"
    assert status["turn_id"] == body["turn_id"]
    assert status["output_message_id"] == body["message_id"]

    messages = client.get("/api/messages").json()
    assert [m["turn_id"] for m in messages] == [body["turn_id"], body["turn_id"]]


def test_stream_done_identifies_committed_turn(client) -> None:
    client.app.state.ctx.reply._limits = DelayLimits(
        first_ms=(0, 0), night_ms=(0, 0), gap_ms=(0, 0),
        stream_first_ms=(0, 0), stream_night_ms=(0, 0), stream_chunk_ms=0,
    )
    response = client.post(
        "/api/chat/stream",
        json={"text": "中午吃什么", "client_msg_id": "turn-stream"},
        headers=HEADERS,
    )
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    done = events[-1]
    assert done["type"] == "done"
    assert done["turn_id"]
    status = client.get("/api/turns/by-client/turn-stream").json()
    assert status["status"] == "committed"
    assert status["output_message_id"] == done["message_id"]


def test_model_failure_is_a_queryable_failed_turn(client) -> None:
    class Broken:
        def complete(self, *args, **kwargs):
            raise LlmError("boom")

    client.app.state.ctx.reply._llm = Broken()
    response = client.post(
        "/api/chat", json={"text": "在吗", "client_msg_id": "turn-failed"}, headers=HEADERS
    )
    assert response.status_code == 503
    status = client.get("/api/turns/by-client/turn-failed").json()
    assert status["status"] == "failed"
    assert status["error_code"] == "llm_unavailable"
    assert status["output_message_id"] is None


def test_concurrent_retry_cannot_generate_twice_or_pick_proactive_message(client) -> None:
    started = Event()
    release = Event()

    class Blocking:
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            started.set()
            assert release.wait(5)
            return Completion("真正的本轮回复")

    model = Blocking()
    ctx = client.app.state.ctx
    ctx.reply._llm = model
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(ctx.reply.reply, "在吗", client_msg_id="same-turn", now=now)
        assert started.wait(5)
        ctx.messages.add_him(
            "主动消息", parts=["主动消息"], mode=Mode.PROACTIVE,
            prompt_version=None, task_id="lunch", usage=None, now=now,
        )
        with pytest.raises(TurnInProgress):
            ctx.reply.reply("在吗", client_msg_id="same-turn", now=now)
        release.set()
        original = first.result(timeout=5)

    repeated = ctx.reply.reply("在吗", client_msg_id="same-turn", now=now)
    assert model.calls == 1
    assert repeated.message_id == original.message_id
    assert repeated.parts[0].text == "真正的本轮回复"
    assert repeated.turn_id == original.turn_id


def test_client_id_reuse_with_different_text_is_rejected(client) -> None:
    ctx = client.app.state.ctx
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    ctx.reply.reply("原文", client_msg_id="same-id", now=now)
    with pytest.raises(TurnConflict):
        ctx.reply.reply("改过的文字", client_msg_id="same-id", now=now)


def test_restart_marks_interrupted_generation_failed(settings) -> None:
    first = create_app(settings)
    turn, created = first.state.ctx.turns.start(
        "尚未生成完", client_msg_id="crashed-turn", now=datetime.now(UTC)
    )
    assert created and turn.status is TurnStatus.GENERATING

    restarted = create_app(settings)
    recovered = restarted.state.ctx.turns.by_client_id("crashed-turn")
    assert recovered is not None
    assert recovered.status is TurnStatus.FAILED
    assert recovered.error_code == "interrupted"
    assert recovered.output_message_id is None


def test_stream_is_committed_even_if_client_never_consumes_events(client) -> None:
    ctx = client.app.state.ctx
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    events = ctx.reply.stream("在吗", client_msg_id="disconnected", now=now)
    turn = ctx.turns.by_client_id("disconnected")
    assert turn is not None and turn.status is TurnStatus.COMMITTED
    assert turn.output_message_id is not None
    events.close()
