"""回合编排：先落库并生成完整答复，再由整段或 SSE 接口交付。"""

from __future__ import annotations

import random
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as clock_time
from typing import Any

from app.core import delay, guard, prompt, scoring
from app.core import disclosure as disclosure_mod
from app.core import situation as situation_mod
from app.core.errors import LlmError, TurnFailed, TurnInProgress
from app.core.models import Action, DelayLimits, DelayPart, Mode, SafetyRules, TurnStatus
from app.ports import (
    ChatModel,
    InboxRepo,
    MemoryStore,
    MessageRepo,
    Notifier,
    PersonaSource,
    StateRepo,
    TurnRepo,
)
from app.services.handoff import HandoffService, status_reply

Event = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReplyResult:
    parts: tuple[DelayPart, ...]
    mode: Mode
    turn_id: str
    message_id: int
    fixed: bool = False
    prompt_version: str | None = None


class ReplyService:
    def __init__(
        self,
        *,
        persona: PersonaSource,
        memory: MemoryStore,
        messages: MessageRepo,
        turns: TurnRepo,
        state: StateRepo,
        inbox: InboxRepo,
        llm: ChatModel,
        notifier: Notifier,
        rules: SafetyRules,
        disclosure: str = "honest",
        owner_name: str = "",
        temperature: float = 0.9,
        max_tokens: int = 400,
        rng: random.Random | None = None,
        limits: DelayLimits | None = None,
    ) -> None:
        self._persona = persona
        self._memory = memory
        self._messages = messages
        self._turns = turns
        self._state = state
        self._llm = llm
        self._handoff = HandoffService(inbox=inbox, notifier=notifier)
        self._rules = rules
        self._disclosure = disclosure
        self._owner_name = owner_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._rng = rng or random.Random()
        self._limits = limits or DelayLimits()

    # ---- 对外 ----
    def disclosure_text(self) -> str:
        return disclosure_mod.notice(self._owner_name)

    def control(self, action: str, *, now: datetime) -> str:
        if action == "mute":
            until = datetime.combine(now.date(), clock_time(23, 59, 59), tzinfo=now.tzinfo)
            self._state.set("muted_until", until.isoformat(), now=now)
            return "行，今天我不吵你。"
        if action == "snooze":
            self._state.set("snoozed_until", (now + timedelta(hours=3)).isoformat(), now=now)
            return "好，你先忙，我晚点再说。"
        if action == "call_owner":
            status = self._handoff.request("call-owner", "她点了「叫他本人」", now=now)
            return status_reply(status)
        if action == "why_ai":
            return self.disclosure_text()
        raise ValueError(f"unknown control action: {action}")

    def reply(self, text: str, *, client_msg_id: str | None, now: datetime) -> ReplyResult:
        turn, created = self._turns.start(text, client_msg_id=client_msg_id, now=now)
        if not created:
            if turn.status is TurnStatus.COMMITTED and turn.output_message_id is not None:
                return ReplyResult(
                    parts=tuple(DelayPart(part, 0) for part in turn.parts),
                    mode=Mode.REPLY,
                    turn_id=turn.turn_id,
                    message_id=turn.output_message_id,
                    fixed=turn.fixed,
                )
            if turn.status is TurnStatus.FAILED:
                raise TurnFailed(turn.error_code or "turn_failed")
            raise TurnInProgress(turn.turn_id)

        try:
            verdict = guard.classify(
                text, now=now, rules=self._rules, owner_name=self._owner_name
            )
            fixed = verdict.action is not Action.REPLY
            prompt_version: str | None = None
            completion = None
            if fixed:
                parts = delay.plan(
                    "\n".join(self._fixed_parts(verdict, now=now)),
                    now=now,
                    rng=self._rng,
                    limits=self._limits,
                )
            else:
                card = self._persona.load()
                hits = scoring.select(text, self._memory.chat_items(), k=4, today=now.date())
                situations = situation_mod.labels(self._memory.private_items(), today=now.date())
                bundle = prompt.build_reply(
                    card=card,
                    hits=hits,
                    situations=situations,
                    history=list(self._messages.recent(12)),
                    now=now,
                    disclosure=self._disclosure,
                    query=text,
                )
                prompt_version = bundle.version
                completion = self._llm.complete(
                    bundle.messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                parts = delay.plan(completion.text, now=now, rng=self._rng, limits=self._limits)
            if not parts:
                raise LlmError("模型返回了空回复")
            message_id = self._turns.commit(
                turn.turn_id,
                parts=[part.text for part in parts],
                fixed=fixed,
                prompt_version=prompt_version,
                usage=completion,
                now=now,
            )
        except LlmError:
            self._turns.fail(turn.turn_id, "llm_unavailable", now=now)
            raise
        except Exception:
            self._turns.fail(turn.turn_id, "internal_error", now=now)
            raise
        return ReplyResult(
            parts=tuple(parts),
            mode=Mode.REPLY,
            turn_id=turn.turn_id,
            message_id=message_id,
            fixed=fixed,
            prompt_version=prompt_version,
        )

    # ---- 流式交付：仅播放已提交的回复 ----
    def stream(self, text: str, *, client_msg_id: str | None, now: datetime) -> Iterator[Event]:
        result = self.reply(text, client_msg_id=client_msg_id, now=now)
        return self.replay(result)

    def replay(self, result: ReplyResult) -> Iterator[Event]:
        yield {
            "type": "start",
            "turn_id": result.turn_id,
            "mode": result.mode.value,
            "fixed": result.fixed,
        }
        for part in result.parts:
            yield {"type": "part", "delay_ms": part.delay_ms}
            if part.delay_ms:
                time.sleep(part.delay_ms / 1000)
            yield {"type": "delta", "text": part.text}
        yield {
            "type": "done",
            "turn_id": result.turn_id,
            "message_id": result.message_id,
            "mode": result.mode.value,
            "fixed": result.fixed,
            "prompt_version": result.prompt_version,
        }

    # ---- 固定回复的状态效果 ----
    def _fixed_parts(self, verdict, *, now: datetime) -> tuple[str, ...]:  # noqa: ANN001
        for key, value in verdict.state.items():
            self._state.set(key, value, now=now)
        if verdict.notify:
            status = self._handoff.request(
                verdict.notify, verdict.context or verdict.action.value, now=now
            )
            if verdict.action is Action.CALL_OWNER:
                return (status_reply(status),)
            if verdict.action is Action.CRISIS:
                return (*verdict.reply_parts, status_reply(status))
        return verdict.reply_parts
