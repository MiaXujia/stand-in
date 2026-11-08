"""迁移：PRAGMA user_version + 顺序执行 migrations/NNN_*.sql。"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.engine import Engine

_COMMENT = re.compile(r"^\s*--.*$", re.M)


def _statements(sql: str) -> list[str]:
    cleaned = _COMMENT.sub("", sql)
    return [s.strip() for s in cleaned.split(";") if s.strip()]


def current_version(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.exec_driver_sql("PRAGMA user_version").scalar_one())


def migrate(engine: Engine, migrations_dir: Path) -> int:
    version = current_version(engine)
    for path in sorted(Path(migrations_dir).glob("*.sql")):
        try:
            number = int(path.name.split("_", 1)[0])
        except ValueError:
            continue
        if number <= version:
            continue
        with engine.begin() as conn:
            for statement in _statements(path.read_text(encoding="utf-8")):
                conn.exec_driver_sql(statement)
            conn.exec_driver_sql(f"PRAGMA user_version = {number}")
        version = number
    return version
