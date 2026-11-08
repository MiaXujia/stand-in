"""聊天接口：/api/chat（整段）与 /api/chat/stream（SSE 流式）。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_ctx, require_session
from app.api.schemas import (
    ChatIn,
    ChatOut,
    ControlIn,
    ControlOut,
    MessageOut,
    PartOut,
    StateOut,
    TurnOut,
)
from app.core.errors import LlmError, TurnConflict, TurnFailed, TurnInProgress

router = APIRouter()


def _sse(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/api/state", response_model=StateOut)
def state(request: Request, _: None = Depends(require_session)) -> StateOut:
    ctx = get_ctx(request)
    now = datetime.now(ctx.settings.tzinfo)
    latest = ctx.messages.recent(1)
    return StateOut(
        app_name=ctx.settings.app_name,
        display_name=ctx.settings.chat_display_name,
        owner_name=ctx.settings.owner_name,
        disclosure=ctx.reply.disclosure_text(),
        muted=ctx.state.muted_until(now=now) is not None,
        snoozed=ctx.state.snoozed_until(now=now) is not None,
        latest_id=latest[-1].id if latest else 0,
    )


@router.get("/api/messages", response_model=list[MessageOut])
def list_messages(
    request: Request,
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    _: None = Depends(require_session),
) -> list[MessageOut]:
    ctx = get_ctx(request)
    return [
        MessageOut(
            id=msg.id,
            role=msg.role,
            mode=msg.mode.value,
            text=msg.text,
            parts=list(msg.parts),
            created_at=msg.created_at.isoformat(),
            turn_id=msg.turn_id,
        )
        for msg in ctx.messages.since(after_id, limit=limit)
    ]


@router.get("/api/turns/by-client/{client_msg_id}", response_model=TurnOut)
def turn_by_client(
    client_msg_id: str, request: Request, _: None = Depends(require_session)
) -> TurnOut:
    turn = get_ctx(request).turns.by_client_id(client_msg_id)
    if turn is None:
        raise HTTPException(status_code=404, detail="turn_not_found")
    return TurnOut(
        turn_id=turn.turn_id,
        client_msg_id=turn.client_msg_id,
        status=turn.status.value,
        input_message_id=turn.input_message_id,
        output_message_id=turn.output_message_id,
        error_code=turn.error_code,
    )


@router.get("/api/turns/{turn_id}", response_model=TurnOut)
def turn_by_id(turn_id: str, request: Request, _: None = Depends(require_session)) -> TurnOut:
    turn = get_ctx(request).turns.by_id(turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail="turn_not_found")
    return TurnOut(
        turn_id=turn.turn_id,
        client_msg_id=turn.client_msg_id,
        status=turn.status.value,
        input_message_id=turn.input_message_id,
        output_message_id=turn.output_message_id,
        error_code=turn.error_code,
    )


@router.post("/api/chat", response_model=ChatOut)
def chat(payload: ChatIn, request: Request, _: None = Depends(require_session)) -> ChatOut:
    ctx = get_ctx(request)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    now = datetime.now(ctx.settings.tzinfo)
    try:
        result = ctx.reply.reply(text, client_msg_id=payload.client_msg_id, now=now)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail="llm_unavailable") from exc
    except TurnConflict as exc:
        raise HTTPException(status_code=409, detail="turn_conflict") from exc
    except TurnInProgress as exc:
        raise HTTPException(status_code=409, detail="turn_in_progress") from exc
    except TurnFailed as exc:
        raise HTTPException(status_code=503, detail="turn_failed") from exc
    return ChatOut(
        parts=[PartOut(text=part.text, delay_ms=part.delay_ms) for part in result.parts],
        mode=result.mode.value,
        turn_id=result.turn_id,
        message_id=result.message_id,
        fixed=result.fixed,
    )


@router.post("/api/control", response_model=ControlOut)
def control(
    payload: ControlIn, request: Request, _: None = Depends(require_session)
) -> ControlOut:
    ctx = get_ctx(request)
    now = datetime.now(ctx.settings.tzinfo)
    return ControlOut(ok=True, message=ctx.reply.control(payload.action, now=now))


@router.post("/api/chat/stream")
def chat_stream(
    payload: ChatIn, request: Request, _: None = Depends(require_session)
) -> StreamingResponse:
    ctx = get_ctx(request)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    now = datetime.now(ctx.settings.tzinfo)
    try:
        events = ctx.reply.stream(text, client_msg_id=payload.client_msg_id, now=now)
    except LlmError as exc:
        raise HTTPException(status_code=503, detail="llm_unavailable") from exc
    except TurnConflict as exc:
        raise HTTPException(status_code=409, detail="turn_conflict") from exc
    except TurnInProgress as exc:
        raise HTTPException(status_code=409, detail="turn_in_progress") from exc
    except TurnFailed as exc:
        raise HTTPException(status_code=503, detail="turn_failed") from exc
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
