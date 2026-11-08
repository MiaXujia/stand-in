"""OpenAI 兼容端点（DeepSeek / OpenAI / Qwen / Ollama / vLLM 都走这里）。"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.core.errors import LlmError
from app.core.models import Completion


class OpenAIChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        from openai import OpenAI  # 延迟导入：fake 模式下不需要它

        self._client = OpenAI(
            api_key=api_key or "missing",
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._model = model

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Completion:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=list(messages),  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - 统一收敛为 LlmError
            raise LlmError(str(exc)) from exc
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage
        return Completion(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Iterator[str]:
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=list(messages),  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                text = getattr(delta, "content", None) if delta else None
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise LlmError(str(exc)) from exc
