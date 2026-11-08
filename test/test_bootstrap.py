from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.bootstrap import run
from app.main import create_app


def test_bootstrap_creates_db_and_env(workspace, settings) -> None:
    report = run(settings)
    assert report.db.exists()
    assert report.schema_version == 3
    assert (workspace / ".env").exists()
    assert "CHAT_TOKEN=" in (workspace / ".env").read_text(encoding="utf-8")
    assert report.fewshots == 2


def test_bootstrap_reports_missing_persona_fields(workspace, settings) -> None:
    report = run(settings)
    assert "年龄" in report.missing
    assert "MODE" not in report.missing


def test_server_startup_does_not_log_chat_token(settings, caplog) -> None:
    with caplog.at_level(logging.INFO), TestClient(create_app(settings)):
        pass
    assert settings.chat_token not in caplog.text
