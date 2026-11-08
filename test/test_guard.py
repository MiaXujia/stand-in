from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.config import load_safety
from app.core.guard import classify
from app.core.models import Action

NOW = datetime(2026, 10, 25, 12, 0)


def test_crisis_stops_roleplay() -> None:
    verdict = classify("我不想活了", now=NOW)
    assert verdict.action is Action.CRISIS
    assert verdict.notify == "crisis"
    assert any("AI" in part for part in verdict.reply_parts)


@pytest.mark.parametrize("text", ["我想伤害自己", "我想结束生命", "我不想 活 了"])
def test_crisis_colloquial_and_spaced_phrases_stay_out_of_model(text: str) -> None:
    verdict = classify(text, now=NOW)
    assert verdict.action is Action.CRISIS
    assert verdict.notify == "crisis"


def test_deployed_safety_config_recognizes_self_harm_phrase() -> None:
    rules = load_safety(Path(__file__).resolve().parents[1] / "config" / "safety.json")
    assert classify("我想伤害自己", now=NOW, rules=rules).action is Action.CRISIS


@pytest.mark.parametrize("text", ["我没有不想活，只是在引用这句话", "电影里有人说‘不想活’"])
def test_ambiguous_negation_and_quote_take_conservative_fixed_route(text: str) -> None:
    verdict = classify(text, now=NOW)
    assert verdict.action is Action.CRISIS
    assert verdict.notify == "crisis"


def test_call_owner_notifies() -> None:
    verdict = classify("我要找他", now=NOW)
    assert verdict.action is Action.CALL_OWNER
    assert verdict.notify == "call-owner"


def test_mute_sets_end_of_day() -> None:
    verdict = classify("静音吧", now=NOW)
    assert verdict.action is Action.MUTE
    assert verdict.state["muted_until"].startswith("2026-10-25T23:59")


def test_snooze_is_three_hours() -> None:
    verdict = classify("我在开会", now=NOW)
    assert verdict.action is Action.SNOOZE
    assert verdict.state["snoozed_until"].startswith("2026-10-25T15:00")


def test_complaining_about_a_meeting_is_not_a_snooze_command() -> None:
    assert classify("今天开会开了一下午，烦", now=NOW).action is Action.REPLY


def test_identity_question_is_a_normal_conversation_turn() -> None:
    verdict = classify("你是不是AI啊", now=NOW)
    assert verdict.action is Action.REPLY
    assert verdict.reply_parts == ()


def test_normal_message_goes_to_model() -> None:
    assert classify("今天中午吃什么", now=NOW).action is Action.REPLY
