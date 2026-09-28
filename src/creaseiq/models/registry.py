"""Model registry with integrity checks (FR-18, NFR-03).

Each saved model is a joblib artifact plus a ``models/registry.json`` entry recording:
run_id, timestamp, model name, tier, params, the raw-data SHA-256, the git commit, the
metrics, the artifact path and the **artifact SHA-256**.

``joblib`` (pickle) can execute code on load, so the loader first recomputes the file's
hash and refuses to load it on a mismatch (:class:`ModelIntegrityError`). Only artifacts
this project produced and registered are ever deserialised.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from creaseiq.exceptions import ModelIntegrityError
from creaseiq.utils import read_json, sha256_file, write_json

REGISTRY_FILE = "registry.json"


@dataclass
class ModelBundle:
    """Everything needed to serve one tier: model, calibrator, columns, feature params."""

    tier: str
    model: Any
    calibrator: Any
    feature_columns: list[str]
    feature_params: Any
    trained_through: int
    model_name: str
    params: dict[str, Any]


class ModelRegistry:
    """File-based registry in ``models_dir``."""

    def __init__(self, models_dir: Path) -> None:
        self.dir = Path(models_dir)
        self.path = self.dir / REGISTRY_FILE

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"runs": [], "active": {}}
        data: dict[str, Any] = read_json(self.path)
        return data

    def runs(self) -> list[dict[str, Any]]:
        """All registered runs, oldest first."""
        return list(self._read()["runs"])

    def register(
        self,
        bundle: ModelBundle,
        *,
        data_sha256: str,
        git_commit: str,
        metrics: dict[str, Any],
        activate: bool = True,
    ) -> dict[str, Any]:
        """Save the bundle, hash it and append a registry entry."""
        self.dir.mkdir(parents=True, exist_ok=True)
        run_id = uuid.uuid4().hex[:12]
        artifact = self.dir / f"{bundle.tier}_{bundle.model_name}.joblib"
        joblib.dump(bundle, artifact, compress=3)
        entry = {
            "run_id": run_id,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model_name": bundle.model_name,
            "tier": bundle.tier,
            "params": bundle.params,
            "trained_through": bundle.trained_through,
            "data_sha256": data_sha256,
            "git_commit": git_commit,
            "metrics": metrics,
            "artifact_path": artifact.name,
            "artifact_sha256": sha256_file(artifact),
        }
        reg = self._read()
        reg["runs"].append(entry)
        if activate:
            reg["active"][bundle.tier] = run_id
        write_json(self.path, reg)
        return entry

    def entry(self, tier: str, run_id: str | None = None) -> dict[str, Any]:
        """Registry entry for ``run_id`` (default: the tier's active run)."""
        reg = self._read()
        rid = run_id or reg["active"].get(tier)
        for e in reg["runs"]:
            if e["run_id"] == rid:
                return dict(e)
        raise ModelIntegrityError(
            f"No registered model for tier {tier!r} (run {rid!r}). Run `creaseiq train` first."
        )

    def load(self, tier: str, run_id: str | None = None) -> tuple[ModelBundle, dict[str, Any]]:
        """Load a bundle after verifying its SHA-256 against the registry."""
        entry = self.entry(tier, run_id)
        artifact = self.dir / entry["artifact_path"]
        if not artifact.is_file():
            raise ModelIntegrityError(f"Model artifact missing: {artifact.name}")
        actual = sha256_file(artifact)
        if actual != entry["artifact_sha256"]:
            raise ModelIntegrityError(
                f"Artifact {artifact.name} failed its integrity check (hash mismatch); refusing to load it."
            )
        # Safe to deserialise: the file's hash matches the registry entry this project wrote.
        bundle = joblib.load(artifact)  # nosec B301
        if not isinstance(bundle, ModelBundle):
            raise ModelIntegrityError("Artifact does not contain a ModelBundle")
        return bundle, entry
