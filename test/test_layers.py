"""分层规矩的可执行版本：扫 import，违反即红。"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

ALLOWED = {
    "core": ("app.core",),
    "services": ("app.core", "app.ports", "app.config", "app.services"),
    "adapters": ("app.core", "app.adapters", "app.ports", "app.settings", "app.config"),
    "api": ("app.",),
}


def _module_name(path: Path) -> str:
    relative = path.relative_to(APP.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def test_layers_respect_dependencies() -> None:
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        parts = path.relative_to(APP).parts
        if len(parts) < 2 or parts[0] not in ALLOWED:
            continue  # main/context/bootstrap/settings 属于装配层
        layer = parts[0]
        allowed = ALLOWED[layer]
        for module in _imports(path):
            if not module.startswith("app."):
                continue
            if not module.startswith(allowed):
                violations.append(f"{_module_name(path)} -> {module}")
    assert not violations, "依赖方向被破坏：\n" + "\n".join(violations)


def test_core_does_not_touch_project_modules() -> None:
    for path in (APP / "core").rglob("*.py"):
        for module in _imports(path):
            if module.startswith("app."):
                assert module.startswith("app.core"), f"{_module_name(path)} 引入了 {module}"
