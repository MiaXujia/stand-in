"""测试夹具：临时人格/记忆/数据库 + 假模型。"""

from __future__ import annotations

import json
import os as _os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

# 这个 Windows 沙箱里 mode=0o700 会生成连自己都读不了的 ACL；pytest 的临时目录
# 与 tempfile 都用 0700，所以统一按默认权限创建。
_original_mkdir = _os.mkdir


def _mkdir_usable(path, mode=0o777, *args, **kwargs):  # noqa: ANN001
    return _original_mkdir(path, 0o777, *args, **kwargs)


_os.mkdir = _mkdir_usable

TOKEN = "t" * 32
PASSWORD = "pw-for-tests"

PERSONA = """# 身份卡
我叫阿哲，{{年龄}} 岁，在杭州做后端。
她叫小满，我叫她宝贝。
{{MODE}}
"""

STYLE = """# 硬性风格规则
## 1. 长度与节奏
连发 2–4 条，每条 5–15 字，最后一条是重点。
## 7. 反例集
```
多喝热水
随便
我早跟你说过
```
"""

FEWSHOT = "\n".join(
    [
        json.dumps(
            {"tags": ["累", "工作"], "her": "今天好累啊", "me": ["怎么了", "谁惹你了"]},
            ensure_ascii=False,
        ),
        json.dumps(
            {"tags": ["吃饭"], "her": "中午吃什么", "me": ["你想吃啥", "我给你点"]},
            ensure_ascii=False,
        ),
    ]
)

PRIVATE_SENTINEL = "她妈住院了别问细节"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for name in ("persona", "memory", "config", "data"):
        (tmp_path / name).mkdir()
    (tmp_path / "persona" / "persona.md").write_text(PERSONA, encoding="utf-8")
    (tmp_path / "persona" / "style-rules.md").write_text(STYLE, encoding="utf-8")
    (tmp_path / "persona" / "fewshot.jsonl").write_text(FEWSHOT, encoding="utf-8")
    (tmp_path / "memory" / "profile.json").write_text("{}", encoding="utf-8")
    _write_json(
        tmp_path / "memory" / "profile.json",
        {
            "items": [
                {
                    "id": "food-001",
                    "text": "不吃香菜",
                    "tags": ["吃饭", "香菜"],
                    "updatedAt": "2026-10-01",
                    "visibility": "chat",
                }
            ]
        },
    )
    for name in ("events", "promises", "bits"):
        _write_json(tmp_path / "memory" / f"{name}.json", {"items": []})
    _write_json(
        tmp_path / "memory" / "private.json",
        {
            "items": [
                {
                    "id": "st-001",
                    "text": PRIVATE_SENTINEL,
                    "visibility": "private",
                    "situation": "压力期",
                    "since": "2026-10-20",
                    "expiresAt": "2030-01-01",
                    "hint": "少开玩笑，多接住，别追问原因。",
                }
            ]
        },
    )
    (tmp_path / "config" / "safety.json").write_text(
        json.dumps({"crisis": ["不想活"], "mute": ["静音"]}),
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text("CHAT_TOKEN=\nOWNER_PASSWORD=\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def settings(workspace: Path) -> Settings:
    return Settings(
        root=workspace,
        chat_token=TOKEN,
        owner_password=PASSWORD,
        llm_provider="fake",
        owner_name="阿哲",
        disclosure="honest",
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    test_client = TestClient(app)
    test_client.get(f"/c/{TOKEN}", follow_redirects=False)
    return test_client
