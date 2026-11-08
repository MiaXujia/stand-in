from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.settings import Settings


def _settings(**overrides) -> Settings:
    base = {"chat_token": "t" * 32, "owner_password": "pw"}
    base.update(overrides)
    return Settings(**base)


def test_any_provider_name_is_accepted() -> None:
    for name in ("DeepSeek", "openai", "qwen", "Ollama", "vllm", "  my-endpoint  "):
        settings = _settings(llm_provider=name)
        assert settings.use_fake_model is False
        assert settings.llm_provider == name.strip().lower()


def test_fake_variants() -> None:
    for name in ("fake", "FAKE", "none", "off", "offline"):
        assert _settings(llm_provider=name).use_fake_model is True


def test_empty_provider_falls_back_to_openai() -> None:
    settings = _settings(llm_provider="")
    assert settings.llm_provider == "openai"
    assert settings.use_fake_model is False


def test_identity_denial_cannot_be_configured() -> None:
    with pytest.raises(ValidationError):
        _settings(disclosure="never")
