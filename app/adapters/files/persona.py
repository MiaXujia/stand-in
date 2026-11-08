"""人格文件加载：persona.md / style-rules.md / fewshot.jsonl。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.models import FewShot, PersonaCard

_PLACEHOLDER = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_banned(style: str) -> tuple[str, ...]:
    """取 style-rules.md 第 7 节代码块里的反例句。"""
    start = style.find("## 7")
    if start < 0:
        return ()
    match = _FENCE.search(style[start:])
    if not match:
        return ()
    return tuple(line.strip() for line in match.group(1).splitlines() if line.strip())


def load_fewshots(path: Path) -> tuple[FewShot, ...]:
    if not path.exists():
        return ()
    shots: list[FewShot] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        data = json.loads(line)
        shots.append(
            FewShot(
                tags=tuple(data.get("tags", [])),
                her=str(data.get("her", "")),
                me=tuple(data.get("me", [])),
            )
        )
    return tuple(shots)


def missing_fields(card: PersonaCard) -> list[str]:
    return list(card.missing)


def _clean_placeholder(raw: str) -> str:
    text = raw.split("，", 1)[0].strip()
    if text.startswith("一句话"):
        return "关系底色"
    return text


class FilePersonaSource:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)

    def load(self) -> PersonaCard:
        identity = _read(self._dir / "persona.md")
        style = _read(self._dir / "style-rules.md")
        banned = parse_banned(style)
        fewshots = load_fewshots(self._dir / "fewshot.jsonl")
        placeholders = {
            _clean_placeholder(match)
            for match in _PLACEHOLDER.findall(identity)
            if match.strip().upper() != "MODE"
        }
        return PersonaCard(
            identity=identity,
            style=style,
            banned=banned,
            fewshots=fewshots,
            missing=tuple(sorted(placeholders)),
        )
