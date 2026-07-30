from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .canonical import canonical_json_bytes, sha256_hex
from .contracts import PredictionRow, TaskPackage
from .templates import CandidateSolver
from .verification import VerificationReport


class AttemptExistsError(FileExistsError):
    pass


@dataclass(frozen=True)
class FreezeManifest:
    package_digest: str
    task_spec: Mapping[str, Any]
    task_spec_digest: str
    solver: Mapping[str, Any]
    solver_digest: str
    verification: Mapping[str, Any]
    verification_digest: str
    runtime_config: Mapping[str, Any]
    dependencies: Mapping[str, str]
    seeds: Mapping[str, int]
    limits: Mapping[str, Any]
    timestamp: str
    version: int = 1
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(f"unsupported freeze manifest version: {self.version}")
        for name in ("task_spec", "solver", "verification", "runtime_config", "dependencies", "seeds", "limits"):
            object.__setattr__(self, name, dict(getattr(self, name)))
        object.__setattr__(self, "digest", sha256_hex(canonical_json_bytes(self.to_data())))

    def to_data(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "package_digest": self.package_digest,
            "task_spec": dict(self.task_spec),
            "task_spec_digest": self.task_spec_digest,
            "solver": dict(self.solver),
            "solver_digest": self.solver_digest,
            "verification": dict(self.verification),
            "verification_digest": self.verification_digest,
            "runtime_config": dict(self.runtime_config),
            "dependencies": dict(self.dependencies),
            "seeds": dict(self.seeds),
            "limits": dict(self.limits),
            "timestamp": self.timestamp,
        }


def freeze_solver(
    package: TaskPackage,
    candidate: CandidateSolver,
    verification: VerificationReport,
    *,
    runtime_config: Mapping[str, Any],
    dependencies: Mapping[str, str],
    seeds: Mapping[str, int],
    limits: Mapping[str, Any],
    timestamp: str = "1970-01-01T00:00:00Z",
) -> FreezeManifest:
    if verification.candidate_id != candidate.candidate_id:
        raise ValueError("candidate and verification identities do not match")
    if not verification.accepted:
        raise ValueError("cannot freeze a candidate that did not pass verification")
    spec_data = candidate.spec.to_data()
    solver_data = candidate.to_data()
    verification_data = verification.to_data()
    return FreezeManifest(
        package_digest=package.package_digest,
        task_spec=spec_data,
        task_spec_digest=sha256_hex(canonical_json_bytes(spec_data)),
        solver=solver_data,
        solver_digest=candidate.digest,
        verification=verification_data,
        verification_digest=sha256_hex(canonical_json_bytes(verification_data)),
        runtime_config=runtime_config,
        dependencies=dependencies,
        seeds=seeds,
        limits=limits,
        timestamp=timestamp,
    )


def _prediction_data(predictions: Sequence[PredictionRow]) -> list[dict[str, Any]]:
    ordered = sorted(predictions, key=lambda row: row.index)
    indexes = [row.index for row in ordered]
    if indexes != list(range(len(ordered))):
        raise ValueError("prediction row indexes must be contiguous and start at zero")
    return [
        {
            "index": row.index,
            "prediction": row.prediction,
            "status": row.status.value,
            "confidence": row.confidence,
            "runtime_ms": row.runtime_ms,
            "error": row.error,
        }
        for row in ordered
    ]


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_first_attempt(
    output_root: Path,
    manifest: FreezeManifest,
    predictions: Sequence[PredictionRow],
) -> Path:
    attempts_root = output_root / "attempts"
    attempts_root.mkdir(parents=True, exist_ok=True)
    target = attempts_root / "attempt-0001"
    if target.exists():
        raise AttemptExistsError(f"first attempt already exists: {target}")
    temporary = attempts_root / f".attempt-0001.{uuid.uuid4().hex}.tmp"
    temporary.mkdir(exist_ok=False)
    try:
        manifest_bytes = canonical_json_bytes(manifest.to_data())
        prediction_bytes = canonical_json_bytes(_prediction_data(predictions))
        prediction_digest = sha256_hex(prediction_bytes)
        attempt_bytes = canonical_json_bytes(
            {
                "attempt_id": "attempt-0001",
                "freeze_digest": manifest.digest,
                "prediction_digest": prediction_digest,
                "supersedes_attempt": None,
            }
        )
        contents = {
            "manifest.json": manifest_bytes,
            "predictions.json": prediction_bytes,
            "ATTEMPT.json": attempt_bytes,
        }
        for name, content in contents.items():
            _atomic_write(temporary / name, content)
        sha_manifest = {name: sha256_hex(content) for name, content in sorted(contents.items())}
        _atomic_write(temporary / "SHA256.json", canonical_json_bytes(sha_manifest))
        _fsync_directory(temporary)
        try:
            os.rename(temporary, target)
        except FileExistsError as exc:
            raise AttemptExistsError(f"first attempt already exists: {target}") from exc
        _fsync_directory(attempts_root)
        return target
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_attempt(attempt_dir: Path) -> None:
    sha_path = attempt_dir / "SHA256.json"
    if not sha_path.is_file():
        raise ValueError("attempt is missing SHA256.json")
    manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("SHA256.json must contain a mapping")
    for relative, expected in manifest.items():
        path = attempt_dir / relative
        if not path.is_file():
            raise ValueError(f"sealed attempt file is missing: {relative}")
        actual = sha256_hex(path.read_bytes())
        if actual != expected:
            raise ValueError(f"digest mismatch for {relative}: {actual} != {expected}")
    actual_files = {path.name for path in attempt_dir.iterdir() if path.is_file() and path.name != "SHA256.json"}
    if actual_files != set(manifest):
        raise ValueError("sealed attempt contains unmanifested or missing files")
    attempt_data = json.loads((attempt_dir / "ATTEMPT.json").read_text(encoding="utf-8"))
    prediction_digest = sha256_hex((attempt_dir / "predictions.json").read_bytes())
    if attempt_data.get("prediction_digest") != prediction_digest:
        raise ValueError("prediction digest mismatch")
    freeze_data = json.loads((attempt_dir / "manifest.json").read_text(encoding="utf-8"))
    freeze_digest = sha256_hex(canonical_json_bytes(freeze_data))
    if attempt_data.get("freeze_digest") != freeze_digest:
        raise ValueError("freeze digest mismatch")
