"""开发/测试用模型：不联网，返回符合人格长度的固定短句。"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence

from app.core.models import Completion


def _fake_reply(messages: Sequence[dict[str, str]]) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    return "在忙吗\n记得吃饭" if "这次的任务" in system else "嗯\n我在\n你说"


class FakeChatModel:
    def __init__(self, reply: str | None = None) -> None:
        self._reply = reply

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Completion:
        text = self._reply or _fake_reply(messages)
        input_chars = sum(len(m.get("content", "")) for m in messages)
        return Completion(
            text=text,
            tokens_in=input_chars // 2,
            tokens_out=len(text) // 2,
        )

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Iterator[str]:
        text = self._reply or _fake_reply(messages)
        for index in range(0, len(text), 2):
            time.sleep(0.04)  # 模拟打字的节奏，方便肉眼验证流式
            yield text[index : index + 2]
