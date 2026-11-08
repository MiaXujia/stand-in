"""纯数据类型：跨层传值只用这里的定义，别处不再出现"无名 dict"。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Literal


class Mode(StrEnum):
    REPLY = "reply"
    PROACTIVE = "proactive"


class Visibility(StrEnum):
    CHAT = "chat"
    PRIVATE = "private"


class ReasonCode(StrEnum):
    DISABLED = "disabled"
    NOT_TODAY = "not-today"
    ALREADY_SENT_TODAY = "already-sent-today"
    DAILY_CAP = "daily-cap"
    NOT_YET = "not-yet"
    MISSED_WINDOW = "missed-window"
    QUIET_HOURS = "quiet-hours"
    MUTED_BY_HER = "muted-by-her"
    SNOOZED = "snoozed"
    AWAITING_HER_REPLY = "awaiting-her-reply"
    MIN_GAP = "min-gap"


class Action(StrEnum):
    REPLY = "reply"
    CRISIS = "crisis"
    CALL_OWNER = "call-owner"
    MUTE = "mute"
    SNOOZE = "snooze"
    RECORD = "record"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TurnStatus(StrEnum):
    GENERATING = "generating"
    COMMITTED = "committed"
    FAILED = "failed"


MemoryKind = Literal["profile", "event", "promise", "bit", "private"]


@dataclass(frozen=True, slots=True)
class MemoryItem:
    id: str
    text: str
    kind: MemoryKind = "profile"
    tags: tuple[str, ...] = ()
    visibility: Visibility = Visibility.CHAT
    updated_at: date | None = None
    expires_at: date | None = None
    due: date | None = None
    annual: bool = False
    situation: str | None = None
    since: date | None = None
    hint: str = ""


@dataclass(frozen=True, slots=True)
class MemoryHit:
    item: MemoryItem
    score: float
    why: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Situation:
    label: str
    since: date | None = None


@dataclass(frozen=True, slots=True)
class DelayPart:
    text: str
    delay_ms: int


@dataclass(frozen=True, slots=True)
class PromptBundle:
    messages: list[dict[str, str]]
    version: str
    sections: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    action: Action
    reply_parts: tuple[str, ...] = ()
    state: dict[str, str] = field(default_factory=dict)
    notify: str | None = None
    context: str = ""


@dataclass(frozen=True, slots=True)
class SafetyRules:
    """兜底词表。默认值放在 core，config/safety.json 只做覆盖。"""

    crisis: tuple[str, ...] = (
        "不想活",
        "活不下去",
        "自杀",
        "自残",
        "割腕",
        "想死",
        "活着没意思",
        "不如死了",
        "伤害自己",
        "结束生命",
    )
    call_owner: tuple[str, ...] = ("找本人", "叫他", "让他来", "我要找他", "我不想跟你说了")
    mute: tuple[str, ...] = ("静音", "别发了", "今天别烦我", "不想聊天")
    snooze: tuple[str, ...] = (
        "我在开会",
        "我先忙",
        "忙完再说",
        "别吵",
        "稍后说",
        "待会聊",
        "晚点聊",
    )
    record: tuple[str, ...] = ("都记下来了", "是不是都记", "监控", "是不是存着", "记录我")


@dataclass(frozen=True, slots=True)
class FewShot:
    tags: tuple[str, ...]
    her: str
    me: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PersonaCard:
    identity: str
    style: str
    banned: tuple[str, ...] = ()
    fewshots: tuple[FewShot, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: int
    role: Literal["her", "him"]
    mode: Mode
    text: str
    parts: tuple[str, ...]
    created_at: datetime
    turn_id: str | None = None


@dataclass(frozen=True, slots=True)
class TurnSnapshot:
    turn_id: str
    client_msg_id: str
    status: TurnStatus
    text: str
    input_message_id: int
    output_message_id: int | None
    error_code: str | None
    fixed: bool
    parts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True, slots=True)
class DelayLimits:
    first_ms: tuple[int, int] = (2000, 8000)
    night_ms: tuple[int, int] = (5000, 15000)
    gap_ms: tuple[int, int] = (800, 2000)
    # 流式：不再等整段生成完，首字前的停顿缩短，节奏交给逐字输出
    stream_first_ms: tuple[int, int] = (1200, 3000)
    stream_night_ms: tuple[int, int] = (2000, 5000)
    stream_chunk_ms: int = 30  # 流式时每个模型分片之间的节奏，避免整段瞬间刷出
    max_parts: int = 4
    max_chars: int = 220
    night_start: int = 22  # 22:00 之后算深夜
    night_end: int = 8
