"""Security checks (NFR-03), collected in one place.

Covered here: no secrets in the repository, no string-built SQL, allow-listed inputs,
tamper-evident model artifacts, safe uploads and exports. Related tests elsewhere:
test_db (injection strings are inert), test_models (tampered artifact is refused),
test_services (upload guards and CSV injection).
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from tests.conftest import ROOT

SRC = ROOT / "src" / "creaseiq"
SECRET_PATTERNS = {
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    "aws key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic api key assignment": re.compile(
        r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
    ),
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".json",
    ".csv",
    ".cfg",
    ".ini",
    ".env",
    ".example",
    ".ipynb",
    ".html",
    ".css",
    ".mmd",
}


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30
        ).stdout
        files = [ROOT / line for line in out.splitlines() if line]
    except (OSError, subprocess.SubprocessError):
        files = [p for p in ROOT.rglob("*") if ".venv" not in p.parts and ".git" not in p.parts]
    return [
        f
        for f in files
        if f.is_file()
        and (f.suffix in TEXT_SUFFIXES or f.name.startswith(".env"))
        and f.stat().st_size < 2_000_000
    ]


def test_no_secrets_committed() -> None:
    hits = []
    for path in _tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}: {name}")
    assert not hits, hits


def test_env_file_is_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines()
    assert not (ROOT / ".env").exists() or ".env" in gitignore


def _calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_no_string_built_sql(path: Path) -> None:
    """``text(...)``, ``execute(...)`` and ``read_sql(...)`` must never receive f-strings or concatenation."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for call in _calls(tree):
        name = (
            call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
        )
        if name in {"text", "execute", "read_sql", "exec_driver_sql"} and call.args:
            arg = call.args[0]
            assert not isinstance(arg, ast.JoinedStr), f"{path.name}:{call.lineno} f-string SQL"
            assert not (isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod))), (
                f"{path.name}:{call.lineno} concatenated SQL"
            )


def test_pickle_loads_are_hash_guarded() -> None:
    """The only deserialisation site is the registry, and it verifies the SHA-256 first."""
    loaders = [
        p
        for p in SRC.rglob("*.py")
        if re.search(r"joblib\.load|pickle\.load", p.read_text(encoding="utf-8"))
    ]
    assert [p.name for p in loaders] == ["registry.py"]
    source = (SRC / "models" / "registry.py").read_text(encoding="utf-8")
    assert source.index("sha256_file(artifact)") < source.index("joblib.load(artifact)")


def test_no_shell_true_or_eval() -> None:
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, path
        tree = ast.parse(text)
        for call in _calls(tree):
            assert getattr(call.func, "id", "") not in {"eval", "exec"}, (
                f"{path.name}:{call.lineno}"
            )


def test_upload_size_limit_configured(settings) -> None:
    assert 0 < int(settings.get("data.upload_max_bytes")) <= 5_000_000
