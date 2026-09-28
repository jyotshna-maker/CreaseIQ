"""Configuration loading (NFR-06: config-driven, reproducible runs).

The single source of truth is ``configs/config.yaml``. Two environment variables may override
it so that deployments need no file edits: ``CREASEIQ_DB_URL`` and ``CREASEIQ_LOG_LEVEL``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from creaseiq.exceptions import ConfigError

_ROOT_MARKER = "pyproject.toml"
_CONFIG_RELPATH = Path("configs") / "config.yaml"


def find_project_root(start: Path | None = None) -> Path:
    """Locate the project root: ``$CREASEIQ_ROOT``, else the nearest parent with pyproject.toml.

    Args:
        start: Directory to start searching from (defaults to this file's directory).

    Returns:
        Absolute path of the project root.

    Raises:
        ConfigError: If no root can be found.
    """
    env_root = os.environ.get("CREASEIQ_ROOT")
    if env_root:
        return Path(env_root).resolve()
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / _ROOT_MARKER).is_file() and (candidate / _CONFIG_RELPATH).is_file():
            return candidate
    # Fall back to the current working directory (e.g. an installed wheel run from the repo).
    cwd = Path.cwd().resolve()
    if (cwd / _CONFIG_RELPATH).is_file():
        return cwd
    raise ConfigError("Could not locate the CreaseIQ project root (configs/config.yaml).")


def load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping, raising :class:`ConfigError` on any problem."""
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a mapping at the top of {path}")
    return data


@dataclass(frozen=True)
class Settings:
    """Immutable view over ``configs/config.yaml`` with path resolution helpers."""

    root: Path
    data: dict[str, Any] = field(repr=False)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Return a nested value by dotted key, e.g. ``settings.get("features.elo.k")``."""
        node: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted_key: str) -> Any:
        """Like :meth:`get` but raise :class:`ConfigError` when the key is absent."""
        sentinel = object()
        value = self.get(dotted_key, sentinel)
        if value is sentinel:
            raise ConfigError(f"Missing required config key: {dotted_key}")
        return value

    def path(self, key: str) -> Path:
        """Resolve ``paths.<key>`` to an absolute path under the project root."""
        return (self.root / str(self.require(f"paths.{key}"))).resolve()

    @property
    def seed(self) -> int:
        """Global random seed."""
        return int(self.require("project.seed"))

    @property
    def db_url(self) -> str:
        """SQLAlchemy URL. Relative SQLite paths are anchored at the project root."""
        url = os.environ.get("CREASEIQ_DB_URL") or str(self.require("database.url"))
        prefix = "sqlite:///"
        if url.startswith(prefix) and not url.startswith(prefix + "/") and ":memory:" not in url:
            rel = url[len(prefix) :]
            if not Path(rel).is_absolute():
                url = prefix + (self.root / rel).resolve().as_posix()
        return url

    @property
    def log_level(self) -> str:
        """Logging level name."""
        return (os.environ.get("CREASEIQ_LOG_LEVEL") or self.get("logging.level", "INFO")).upper()


def load_settings(root: Path | None = None) -> Settings:
    """Load settings from ``<root>/configs/config.yaml``."""
    project_root = (root or find_project_root()).resolve()
    return Settings(root=project_root, data=load_yaml(project_root / _CONFIG_RELPATH))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings (use :func:`load_settings` in tests)."""
    return load_settings()
