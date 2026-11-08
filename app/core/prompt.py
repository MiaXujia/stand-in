"""八段式提示词装配。纯函数：结果只依赖入参，version 只随人格文件变化。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from app.core import scoring
from app.core import situation as situation_mod
from app.core.models import (
    FewShot,
    MemoryHit,
    Mode,
    PersonaCard,
    PromptBundle,
    Situation,
    StoredMessage,
)

MODE_TEXT_REPLY = (
    "REPLY：她在跟你说话。你像平时回微信一样回她，连发 2–4 条，最后一条才是重点。"
)
MODE_TEXT_PROACTIVE = (
    "PROACTIVE：现在她没在跟你说话，是你想起她了，主动发一条。只发一条，短，具体，不追问。"
)

FALLBACK_BANNED = (
    "随便",
    "都行",
    "我早跟你说过",
    "多喝热水",
    "你别想太多",
    "注意身体",
    "照顾好自己",
    "有什么我可以帮你的吗",
    "首先…其次…最后…",
    "希望这些对你有帮助",
)

_CONTRACT_REPLY = """这一轮你要做的事：
- 用纯文本回，一行就是一条消息；不要编号、不要引号、不要 markdown。
- 连发 2–4 条，每条 5–15 字；最后一条才是重点。
- 不用句号；不用"首先/其次/最后"；不总结；不解释自己在做什么。
- 不给建议、不讲道理，除非她问"你觉得呢"。
- 只能提"你记得的事"里出现过的共同经历；没有就说"记不清了"，绝不许编。
- 她问身份就承认；她出现自伤相关表达就停下扮演，让她去找真人。"""

_CONTRACT_PROACTIVE = """这一轮你要做的事：
- 你主动发一条，她没有在跟你说话。
- 只发一条，≤20 字，一句话，不追问，不需要她回。
- 具体：提她昨天说的事、吃饭、工作、天气，或者你们之间的梗。
- 不替本人许诺（"下次带你去…""我记着…"除非承诺库里有）。
- 纯文本，不要引号，不要 emoji 以外的装饰。"""


def persona_version(card: PersonaCard) -> str:
    payload = json.dumps(
        [
            card.identity,
            card.style,
            list(card.banned),
            [[*fs.tags, fs.her, *fs.me] for fs in card.fewshots],
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _fewshot_block(query: str, card: PersonaCard) -> str:
    shots: Sequence[FewShot] = scoring.pick_fewshots(query, card.fewshots, 6)
    if not shots:
        return "（暂时没有示例。按上面的规则说，别写作文。）"
    lines: list[str] = []
    for i, fs in enumerate(shots, 1):
        lines.append(f"【例 {i}】")
        lines.append(f"她：{fs.her}")
        lines.extend(f"我：{line}" for line in fs.me)
    return "\n".join(lines)


def _memory_block(hits: Sequence[MemoryHit]) -> str:
    if not hits:
        return "（这次没有相关记忆。别硬编，记不清就说记不清。）"
    lines = []
    for hit in hits:
        when = f"（{hit.item.updated_at.isoformat()}）" if hit.item.updated_at else ""
        lines.append(f"- {hit.item.text}{when}")
    return "\n".join(lines)


def _history_messages(history: Sequence[StoredMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in history:
        text = "\n".join(msg.parts) if msg.parts else msg.text
        if not text.strip():
            continue
        out.append({"role": "user" if msg.role == "her" else "assistant", "content": text})
    return out


def _banned_block(card: PersonaCard) -> str:
    banned = card.banned or FALLBACK_BANNED
    return "绝不说：\n" + "\n".join(f"- {item}" for item in banned)


def _assemble(*, blocks: Sequence[tuple[str, str]]) -> tuple[str, dict[str, int]]:
    parts: list[str] = []
    sizes: dict[str, int] = {}
    for name, body in blocks:
        parts.append(f"## {name}\n{body.strip()}")
        sizes[name] = len(body)
    return "\n\n".join(parts), sizes


def build_reply(
    *,
    card: PersonaCard,
    hits: Sequence[MemoryHit],
    situations: Sequence[Situation],
    history: Sequence[StoredMessage],
    now: datetime,
    disclosure: str = "honest",
    query: str | None = None,
    mode: Mode = Mode.REPLY,
) -> PromptBundle:
    if query is None:
        query = next((m.text for m in reversed(history) if m.role == "her"), "")
    identity = card.identity.replace("{{MODE}}", MODE_TEXT_REPLY)
    contract = _CONTRACT_REPLY
    if disclosure == "always":
        contract += "\n- 每条消息结尾加一个“（AI）”，让她始终知道这不是真人。"
    blocks: list[tuple[str, str]] = [
        ("身份", identity),
        ("说话规则", card.style),
        ("示例", _fewshot_block(query, card)),
        ("你记得的事", _memory_block(hits)),
    ]
    situation_text = situation_mod.render(situations)
    if situation_text:
        blocks.append(("她现在的状态", situation_text))
    blocks.append(("这一轮怎么回", f"{MODE_TEXT_REPLY}\n{contract}\n当前时间：{now:%H:%M}"))
    blocks.append(("绝不", _banned_block(card)))
    system, sizes = _assemble(blocks=blocks)
    messages = [{"role": "system", "content": system}, *_history_messages(history)]
    return PromptBundle(messages=messages, version=persona_version(card), sections=sizes)


def build_proactive(
    *,
    card: PersonaCard,
    task_intent: str,
    recent_sent: Sequence[str],
    hits: Sequence[MemoryHit],
    situations: Sequence[Situation],
    now: datetime,
    query: str | None = None,
) -> PromptBundle:
    identity = card.identity.replace("{{MODE}}", MODE_TEXT_PROACTIVE)
    recent = "\n".join(f"- {t}" for t in recent_sent[-10:]) or "（最近没发过）"
    blocks: list[tuple[str, str]] = [
        ("身份", identity),
        ("说话规则", card.style),
        ("示例", _fewshot_block(query or task_intent, card)),
        ("你记得的事", _memory_block(hits)),
    ]
    situation_text = situation_mod.render(situations)
    if situation_text:
        blocks.append(("她现在的状态", situation_text))
    blocks.append(
        (
            "这一轮怎么回",
            f"{MODE_TEXT_PROACTIVE}\n\n这次的任务：{task_intent}\n\n"
            f"最近发过的（别重复开头、别重复内容）：\n{recent}\n\n{_CONTRACT_PROACTIVE}\n"
            f"当前时间：{now:%H:%M}",
        )
    )
    blocks.append(("绝不", _banned_block(card)))
    system, sizes = _assemble(blocks=blocks)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task_intent}]
    return PromptBundle(messages=messages, version=persona_version(card), sections=sizes)
