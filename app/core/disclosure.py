"""对她说明身份、记录和数据操作状态的统一文案。"""

from __future__ import annotations


def notice(owner_name: str = "") -> str:
    owner = owner_name or "他"
    return f"这是{owner}做的 AI，用他的语气跟你说话。{owner}本人能看到这段对话。"


def record_reply(owner_name: str = "") -> tuple[str, ...]:
    owner = owner_name or "他"
    return (
        f"这段对话会保存，{owner}本人能看到。",
        "目前没有自助删除入口。如果想删除，请直接联系他。",
    )
