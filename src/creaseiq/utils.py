"""Small, dependency-free helpers shared across layers."""

from __future__ import annotations

import hashlib
import json
import random
import shutil

# subprocess is used only to read the git commit hash, with a fixed argv.
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Return the hex SHA-256 digest of a file (FR-18, NFR-03)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_everything(seed: int) -> np.random.Generator:
    """Seed Python's and NumPy's global RNGs and return a fresh Generator (NFR-06)."""
    random.seed(seed)
    np.random.seed(seed)  # legacy global seed, for third-party code paths
    return np.random.default_rng(seed)


def git_commit(root: Path) -> str:
    """Return the current git commit hash, or ``"unknown"`` outside a repository."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        # Fixed argv with an absolute executable path and no user input.
        out = subprocess.run(  # noqa: S603  # nosec B603
            [git, "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def write_json(path: Path, payload: Any) -> None:
    """Write JSON deterministically (sorted keys, UTF-8, trailing newline)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return obj.as_posix()
    return str(obj)
