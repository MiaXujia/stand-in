"""兜底闸门：危机 / 找本人 / 静音 / 在忙 / 记录。

原则：这五类一律走固定话术，不调模型；只有 REPLY 才交给 LLM。
身份问题走普通对话；prompt 要求如实回答。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time, timedelta

from app.core import disclosure as disclosure_mod
from app.core.models import Action, GuardVerdict, SafetyRules


def _norm(text: str) -> str:
    return "".join(text.lower().split())


def _hit(normalized: str, patterns: Sequence[str]) -> bool:
    return any(p and p in normalized for p in patterns)


def classify(
    text: str,
    *,
    now: datetime,
    state: dict[str, str] | None = None,
    rules: SafetyRules | None = None,
    owner_name: str = "",
) -> GuardVerdict:
    rules = rules or SafetyRules()
    norm = _norm(text)
    ctx = text[:200]

    if _hit(norm, rules.crisis):
        return GuardVerdict(
            action=Action.CRISIS,
            reply_parts=(
                "我先不装了。我是他做的 AI，不是他本人。",
                "你现在需要真人：给他打电话，或者找身边能马上到你身边的人。",
                "如果涉及人身安全，打 120。",
            ),
            notify="crisis",
            context=ctx,
        )

    if _hit(norm, rules.call_owner):
        return GuardVerdict(
            action=Action.CALL_OWNER,
            reply_parts=("我记下了你的请求，但还不能确认消息送到他。请直接联系他。",),
            notify="call-owner",
            context=ctx,
        )

    if _hit(norm, rules.mute):
        end_of_day = datetime.combine(now.date(), time(23, 59, 59), tzinfo=now.tzinfo)
        return GuardVerdict(
            action=Action.MUTE,
            reply_parts=("行，今天我不吵你。",),
            state={"muted_until": end_of_day.isoformat()},
        )

    if _hit(norm, rules.snooze):
        snoozed = now + timedelta(hours=3)
        return GuardVerdict(
            action=Action.SNOOZE,
            reply_parts=("好，你先忙，我晚点再说。",),
            state={"snoozed_until": snoozed.isoformat()},
        )

    if _hit(norm, rules.record):
        return GuardVerdict(
            action=Action.RECORD,
            reply_parts=disclosure_mod.record_reply(owner_name),
        )

    return GuardVerdict(action=Action.REPLY)
