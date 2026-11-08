"""依赖装配：把 adapters 接到 services 上。只有这里认识全部实现。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from app.adapters.files.memory import FileMemoryStore
from app.adapters.files.persona import FilePersonaSource
from app.adapters.llm.factory import build_chat_model
from app.adapters.notify.owner import OwnerNotifier
from app.adapters.sqlite import MIGRATIONS_DIR
from app.adapters.sqlite.engine import make_engine
from app.adapters.sqlite.migrate import migrate
from app.adapters.sqlite.repositories import (
    SqliteInboxRepo,
    SqliteMessageRepo,
    SqliteProactiveRepo,
    SqliteSendLogRepo,
    SqliteStateRepo,
    SqliteTurnRepo,
)
from app.config import load_safety
from app.core.models import SafetyRules
from app.ports import ChatModel
from app.services.reply import ReplyService
from app.settings import Settings


@dataclass
class AppContext:
    settings: Settings
    engine: Engine
    messages: SqliteMessageRepo
    turns: SqliteTurnRepo
    state: SqliteStateRepo
    proactive: SqliteProactiveRepo
    send_log: SqliteSendLogRepo
    inbox: SqliteInboxRepo
    memory: FileMemoryStore
    persona: FilePersonaSource
    llm: ChatModel
    notifier: OwnerNotifier
    rules: SafetyRules
    reply: ReplyService


def build_context(settings: Settings) -> AppContext:
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.backup_path.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.db_path)
    migrate(engine, MIGRATIONS_DIR)

    messages = SqliteMessageRepo(engine)
    turns = SqliteTurnRepo(engine)
    turns.recover_incomplete(now=datetime.now(UTC))
    state = SqliteStateRepo(engine)
    proactive = SqliteProactiveRepo(engine)
    send_log = SqliteSendLogRepo(engine)
    inbox = SqliteInboxRepo(engine)

    memory = FileMemoryStore(settings.memory_path)
    persona = FilePersonaSource(settings.persona_path)
    llm = build_chat_model(settings)
    notifier = OwnerNotifier(webhook=settings.owner_webhook)
    rules = load_safety(settings.config_path / "safety.json")

    reply = ReplyService(
        persona=persona,
        memory=memory,
        messages=messages,
        turns=turns,
        state=state,
        inbox=inbox,
        llm=llm,
        notifier=notifier,
        rules=rules,
        disclosure=settings.disclosure,
        owner_name=settings.owner_name,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    return AppContext(
        settings=settings,
        engine=engine,
        messages=messages,
        turns=turns,
        state=state,
        proactive=proactive,
        send_log=send_log,
        inbox=inbox,
        memory=memory,
        persona=persona,
        llm=llm,
        notifier=notifier,
        rules=rules,
        reply=reply,
    )
