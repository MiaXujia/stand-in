"""按配置挑模型实现：换 provider 只改 .env。"""

from __future__ import annotations

from app.adapters.llm.fake import FakeChatModel
from app.adapters.llm.openai_compat import OpenAIChatModel
from app.ports import ChatModel
from app.settings import Settings


def build_chat_model(settings: Settings) -> ChatModel:
    if settings.use_fake_model:
        return FakeChatModel()
    if not settings.api_key:
        raise RuntimeError(
            f"LLM_PROVIDER={settings.llm_provider} 但没有填 DEEPSEEK_API_KEY。"
            "要么在 .env 里填 key，要么先设 LLM_PROVIDER=fake 跑通流程。"
        )
    return OpenAIChatModel(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        timeout=settings.llm_timeout,
    )
