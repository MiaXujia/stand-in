"""请求/响应 DTO：唯一出入边界，别处不再手搓 dict。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    client_msg_id: str | None = Field(default=None, max_length=64)


class PartOut(BaseModel):
    text: str
    delay_ms: int


class ChatOut(BaseModel):
    parts: list[PartOut]
    mode: Literal["reply", "proactive"]
    turn_id: str
    message_id: int
    fixed: bool = False


class MessageOut(BaseModel):
    id: int
    role: Literal["her", "him"]
    mode: str
    text: str
    parts: list[str]
    created_at: str
    turn_id: str | None = None


class TurnOut(BaseModel):
    turn_id: str
    client_msg_id: str
    status: Literal["generating", "committed", "failed"]
    input_message_id: int
    output_message_id: int | None
    error_code: str | None


class StateOut(BaseModel):
    app_name: str
    display_name: str
    owner_name: str
    disclosure: str
    muted: bool
    snoozed: bool
    latest_id: int


class ControlIn(BaseModel):
    action: Literal["mute", "snooze", "call_owner", "why_ai"]


class ControlOut(BaseModel):
    ok: bool = True
    message: str


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class LoginOut(BaseModel):
    ok: bool


class HealthOut(BaseModel):
    ok: bool
    db: str
    jobs: int
    version: str
