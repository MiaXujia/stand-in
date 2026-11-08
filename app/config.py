"""配置模型：messaging.json（排班）与 safety.json（词表）。"""

from __future__ import annotations

import json
from datetime import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.models import SafetyRules


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class QuietHours(_Model):
    start: time = time(22, 30)
    end: time = time(8, 30)


class Task(_Model):
    id: str
    label: str = ""
    at: time
    window_minutes: int = 45
    days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    intent: str = ""
    max_per_day: int = 1
    enabled: bool = True
    ignore_quiet_hours: bool = False

    @field_validator("days")
    @classmethod
    def _check_days(cls, value: list[int]) -> list[int]:
        cleaned = sorted({d for d in value if 1 <= d <= 7})
        if not cleaned:
            raise ValueError("days 不能为空（1=周一 … 7=周日）")
        return cleaned


class MessagingConfig(_Model):
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    min_gap_minutes: int = 120
    max_proactive_per_day: int = 3
    no_reply_no_second_message: bool = True
    default_window_minutes: int = 45
    tasks: list[Task] = Field(default_factory=list)


class SafetyRulesModel(_Model):
    crisis: list[str] = Field(default_factory=lambda: list(SafetyRules().crisis))
    call_owner: list[str] = Field(default_factory=lambda: list(SafetyRules().call_owner))
    mute: list[str] = Field(default_factory=lambda: list(SafetyRules().mute))
    snooze: list[str] = Field(default_factory=lambda: list(SafetyRules().snooze))
    record: list[str] = Field(default_factory=lambda: list(SafetyRules().record))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_messaging(path: Path) -> MessagingConfig:
    if not path.exists():
        raise FileNotFoundError(f"缺少排班配置：{path}")
    return MessagingConfig.model_validate(_read_json(path))


def load_safety(path: Path) -> SafetyRules:
    if not path.exists():
        return SafetyRules()
    model = SafetyRulesModel.model_validate(_read_json(path))
    return SafetyRules(
        crisis=tuple(model.crisis),
        call_owner=tuple(model.call_owner),
        mute=tuple(model.mute),
        snooze=tuple(model.snooze),
        record=tuple(model.record),
    )
