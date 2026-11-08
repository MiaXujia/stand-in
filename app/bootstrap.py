"""首次启动：建目录、生成 .env、跑迁移、检查人格缺项。

  python -m app.bootstrap
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.files.memory import FILES
from app.adapters.files.persona import FilePersonaSource
from app.adapters.sqlite import MIGRATIONS_DIR
from app.adapters.sqlite.engine import make_engine
from app.adapters.sqlite.migrate import migrate
from app.config import load_messaging
from app.settings import Settings, get_settings

_TOKEN = re.compile(r"^CHAT_TOKEN=.*$", re.M)
_PASSWORD = re.compile(r"^OWNER_PASSWORD=.*$", re.M)


@dataclass
class Report:
    root: Path
    db: Path
    schema_version: int
    env_created: bool
    token_generated: bool
    password_generated: bool
    chat_token: str
    missing: list[str] = field(default_factory=list)
    fewshots: int = 0
    llm_provider: str = ""
    templates: list[str] = field(default_factory=list)
    memory: dict[str, int] = field(default_factory=dict)
    tasks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_api_key: bool = False
    fake_model: bool = False


def ensure_dirs(settings: Settings) -> None:
    for path in (
        settings.data_path,
        settings.backup_path,
        settings.config_path,
        settings.persona_path,
        settings.memory_path,
    ):
        path.mkdir(parents=True, exist_ok=True)


def _fill(pattern: re.Pattern[str], text: str, value: str) -> tuple[str, bool]:
    match = pattern.search(text)
    if match and not match.group(0).split("=", 1)[1].strip():
        return pattern.sub(f"{match.group(0).split('=', 1)[0]}={value}", text), True
    if not match:
        return text.rstrip() + f"\n{pattern.pattern.strip('^$')}={value}\n", True
    return text, False


def ensure_env(settings: Settings) -> tuple[bool, str, str]:
    """返回 (是否新建, 生成的 token, 生成的口令)；只补空值，不覆盖已有值。"""
    env_path = settings.root / ".env"
    example = settings.root / ".env.example"
    created = not env_path.exists()
    if created:
        text = example.read_text(encoding="utf-8") if example.exists() else ""
    else:
        text = env_path.read_text(encoding="utf-8")

    token = ""
    password = ""
    text, token_made = _fill(_TOKEN, text, secrets.token_urlsafe(32))
    if token_made:
        token = _TOKEN.search(text).group(0).split("=", 1)[1]  # type: ignore[union-attr]
    text, password_made = _fill(_PASSWORD, text, secrets.token_urlsafe(9))
    if password_made:
        password = _PASSWORD.search(text).group(0).split("=", 1)[1]  # type: ignore[union-attr]

    if created or token_made or password_made:
        env_path.write_text(text, encoding="utf-8")
    return created, token, password


def copy_templates(settings: Settings) -> list[str]:
    """从 *-example 复制缺失的私人文件；已存在的绝不覆盖。"""
    copied: list[str] = []
    pairs = (
        ("persona-example", settings.persona_path),
        ("memory-example", settings.memory_path),
    )
    for source_name, target_dir in pairs:
        source = settings.root / source_name
        if not source.is_dir():
            continue
        for item in sorted(source.iterdir()):
            if not item.is_file():
                continue
            target = target_dir / item.name
            if not target.exists():
                shutil.copy2(item, target)
                copied.append(f"{source_name}/{item.name}")
    messaging = settings.config_path / "messaging.json"
    example = settings.config_path / "messaging.example.json"
    if not messaging.exists() and example.exists():
        shutil.copy2(example, messaging)
        copied.append("config/messaging.json")
    return copied


def _memory_status(settings: Settings) -> tuple[dict[str, int], list[str]]:
    """统计 items 条数；顺便抓"填到 _examples 里"这种最常见的错误。"""
    counts: dict[str, int] = {}
    warnings: list[str] = []
    for kind, name in FILES.items():
        path = settings.memory_path / name
        if not path.exists():
            counts[kind] = 0
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", []) if isinstance(data, dict) else data
        counts[kind] = len(items)
        examples = data.get("_examples", []) if isinstance(data, dict) else []
        if not items and examples:
            warnings.append(
                f"memory/{name}: _examples 有 {len(examples)} 条，但 items 是空的"
                "（程序只读 items，搬过去才生效）"
            )
    return counts, warnings


def run(settings: Settings) -> Report:
    ensure_dirs(settings)
    created, token, password = ensure_env(settings)
    templates = copy_templates(settings)

    engine = make_engine(settings.db_path)
    version = migrate(engine, MIGRATIONS_DIR)
    card = FilePersonaSource(settings.persona_path).load()
    memory, warnings = _memory_status(settings)
    tasks: list[str] = []
    messaging_file = settings.config_path / "messaging.json"
    if messaging_file.exists():
        tasks = [task.id for task in load_messaging(messaging_file).tasks if task.enabled]

    return Report(
        root=settings.root,
        db=settings.db_path,
        schema_version=version,
        env_created=created,
        token_generated=bool(token),
        password_generated=bool(password),
        chat_token=settings.chat_token or token,
        missing=list(card.missing),
        fewshots=len(card.fewshots),
        llm_provider=settings.llm_provider,
        templates=templates,
        memory=memory,
        tasks=tasks,
        warnings=warnings,
        has_api_key=bool(settings.api_key),
        fake_model=settings.use_fake_model,
    )


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    settings = get_settings()
    report = run(settings)

    print(f"root        {report.root}")
    print(f"db          {report.db}  (schema v{report.schema_version})")
    if report.env_created:
        print(".env        已生成（CHAT_TOKEN / OWNER_PASSWORD 已写入，别提交）")
    elif report.token_generated or report.password_generated:
        print(".env        补齐了空的 CHAT_TOKEN / OWNER_PASSWORD")

    if report.chat_token:
        print(f"入口        http://127.0.0.1:8000/c/{report.chat_token}")
    else:
        print("入口        CHAT_TOKEN 仍为空：检查 .env 或环境变量")

    if report.missing:
        print(f"人格缺项    {len(report.missing)} 处：{'、'.join(report.missing)}")
    else:
        print("人格缺项    无")
    print(f"fewshot     {report.fewshots} 条" + ("（建议 40–60）" if report.fewshots < 40 else ""))
    if report.templates:
        print(f"模板        已补：{'、'.join(report.templates)}")
    if report.memory:
        print("内容        " + " · ".join(f"{k} {v}" for k, v in report.memory.items()))
    if report.tasks:
        print(f"排班        {len(report.tasks)} 条：{', '.join(report.tasks)}")
    for warning in report.warnings:
        print(f"⚠  {warning}")

    if not report.has_api_key:
        suffix = "（当前 fake：能跑，但不会像你）" if report.fake_model else "，启动会失败"
        print(f"模型        DEEPSEEK_API_KEY 未填{suffix}")
    elif report.fake_model:
        print("模型        key 已填，但 LLM_PROVIDER 还是 fake（改成 openai / deepseek 才走真模型）")
    else:
        print(f"模型        {report.llm_provider} · {settings.base_url} · {settings.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
