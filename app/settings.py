"""运行配置：全部来自 .env，路径全部由 STANDIN_ROOT 推导（代码里没有绝对路径）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    """仓库根目录：app/settings.py 的上两级。"""
    return Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    root: Path = Field(
        default_factory=repo_root,
        validation_alias=AliasChoices("STANDIN_ROOT", "ROOT"),
    )

    # 入口
    chat_token: str = ""
    app_name: str = "stand-in"
    display_name: str = ""  # 她看到的顶栏名字；留空则用 OWNER_NAME
    public_url: str = "http://127.0.0.1:8000"
    # 本机直连（127.0.0.1 且没有经过反代）时自动登录，省得每次拼 token 链接
    local_auto_login: bool = True

    # 本人
    owner_name: str = ""
    owner_password: str = ""
    owner_webhook: str = ""

    # 行为
    tz: str = "Asia/Shanghai"
    disclosure: Literal["honest", "always"] = "honest"
    log_level: str = "INFO"

    # 模型：只要不是 fake，一律按 OpenAI 兼容端点处理
    # （DeepSeek / OpenAI / Qwen / Ollama / vLLM 都行，名字只是标签）
    llm_provider: str = "openai"
    api_key: str = Field(
        default="", validation_alias=AliasChoices("DEEPSEEK_API_KEY", "API_KEY", "LLM_API_KEY")
    )
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    llm_temperature: float = 0.9
    llm_max_tokens: int = 400
    llm_timeout: float = 30.0

    # 前后端分离部署时的白名单
    cors_origins: str = ""

    # 目录覆盖（相对 root 或绝对路径）
    data_dir: str | None = None
    persona_dir: str | None = None
    memory_dir: str | None = None
    config_dir: str | None = None
    web_dist: str | None = None

    @field_validator("root", mode="before")
    @classmethod
    def _expand_root(cls, value: object) -> Path:
        if value in (None, ""):
            return repo_root()
        return Path(str(value)).expanduser().resolve()

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> str:
        return str(value or "openai").strip().lower()

    def _resolve(self, override: str | None, default: str) -> Path:
        raw = Path(override) if override else Path(default)
        return raw if raw.is_absolute() else (self.root / raw).resolve()

    @property
    def use_fake_model(self) -> bool:
        return self.llm_provider in {"fake", "none", "off", "offline"}

    @property
    def chat_display_name(self) -> str:
        return self.display_name.strip() or self.owner_name.strip() or self.app_name

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def data_path(self) -> Path:
        return self._resolve(self.data_dir, "data")

    @property
    def db_path(self) -> Path:
        return self.data_path / "app.db"

    @property
    def backup_path(self) -> Path:
        return self.data_path / "backups"

    @property
    def persona_path(self) -> Path:
        return self._resolve(self.persona_dir, "persona")

    @property
    def memory_path(self) -> Path:
        return self._resolve(self.memory_dir, "memory")

    @property
    def config_path(self) -> Path:
        return self._resolve(self.config_dir, "config")

    @property
    def web_dist_path(self) -> Path:
        return self._resolve(self.web_dist, "web/dist")

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
