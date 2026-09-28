"""Layered architecture enforced by an AST check (NFR-05). Mirrors the import-linter contract.

Allowed dependency direction (downward only):
app/cli → services → analytics|features|models|simulation|reporting|viz → data|db → config|logging_setup|exceptions|utils
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "creaseiq"
LAYERS: dict[str, int] = {
    "app": 4, "cli": 4, "__main__": 4,
    "services": 3,
    "analytics": 2, "features": 2, "models": 2, "simulation": 2, "reporting": 2, "viz": 2,
    "data": 1, "db": 1,
    "config": 0, "logging_setup": 0, "exceptions": 0, "utils": 0, "__init__": 0,
}  # fmt: skip


def _layer_of(module: str) -> int | None:
    parts = module.split(".")
    if parts[0] != "creaseiq":
        return None
    if len(parts) == 1:
        return 0
    return LAYERS.get(parts[1])


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    return ".".join(rel.parts)


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_imports_point_downward(path: Path) -> None:
    me = _layer_of(_module_name(path))
    assert me is not None
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            targets = [node.module]
        elif isinstance(node, ast.Import):
            targets = [a.name for a in node.names]
        for target in targets:
            other = _layer_of(target)
            if other is not None and target != "creaseiq":
                assert other <= me, (
                    f"{_module_name(path)} (layer {me}) imports {target} (layer {other})"
                )


def test_every_package_is_assigned_a_layer() -> None:
    for child in SRC.iterdir():
        name = child.stem if child.is_file() else child.name
        if child.suffix == ".py" or (child.is_dir() and (child / "__init__.py").exists()):
            assert name in LAYERS, name


def test_public_functions_have_docstrings_and_annotations() -> None:
    missing = []
    for path in SRC.rglob("*.py"):
        if "app" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.ClassDef) and not node.name.startswith("_"):
                if ast.get_docstring(node) is None:
                    missing.append(f"{path.name}:{node.name} docstring")
                if isinstance(node, ast.FunctionDef) and node.returns is None:
                    missing.append(f"{path.name}:{node.name} return annotation")
    assert not missing, missing
