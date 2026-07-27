#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence


def canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def generate_predictions(
    examples: Sequence[Mapping[str, Any]],
    solver: Callable[[str], str | None],
    task_name: str,
    output_dir: Path,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, example in enumerate(examples):
        prompt = str(example["input"])
        started = time.perf_counter()
        try:
            prediction = solver(prompt)
            error = None
        except Exception as exc:
            prediction = None
            error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "index": index,
                "input_sha256": sha256_bytes(prompt.encode("utf-8")),
                "prediction": None if prediction is None else str(prediction).strip(),
                "error": error,
                "latency_seconds": time.perf_counter() - started,
            }
        )

    payload: dict[str, Any] = {
        "protocol": "targets-hidden-during-generation",
        "task": task_name,
        "metadata": dict(metadata),
        "rows": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(payload)
    (output_dir / "predictions.json").write_bytes(raw)
    (output_dir / "predictions.sha256").write_text(sha256_bytes(raw) + "\n", encoding="utf-8")
    return payload


def score_predictions(
    examples: Sequence[Mapping[str, Any]],
    prediction_path: Path,
    seal_path: Path,
    score_path: Path,
    equivalence: Callable[[str, str], bool] | None = None,
) -> dict[str, Any]:
    raw = prediction_path.read_bytes()
    expected = seal_path.read_text(encoding="utf-8").strip()
    actual = sha256_bytes(raw)
    if actual != expected:
        raise ValueError(f"prediction seal mismatch: expected {expected}, got {actual}")

    payload = json.loads(raw)
    rows = payload["rows"]
    if len(rows) != len(examples):
        raise ValueError(f"prediction/example length mismatch: {len(rows)} != {len(examples)}")

    scored_rows: list[dict[str, Any]] = []
    for index, (example, row) in enumerate(zip(examples, rows)):
        prompt = str(example["input"])
        prompt_hash = sha256_bytes(prompt.encode("utf-8"))
        if row.get("index") != index or row.get("input_sha256") != prompt_hash:
            raise ValueError(f"prediction/input mismatch at index {index}")
        prediction = row.get("prediction")
        target = str(example["target"]).strip()
        correct = False
        if prediction is not None:
            pred_text = str(prediction).strip()
            correct = equivalence(pred_text, target) if equivalence else pred_text == target
        scored_rows.append(
            {
                "index": index,
                "prediction": prediction,
                "target": target,
                "correct": bool(correct),
                "error": row.get("error"),
            }
        )

    n = len(scored_rows)
    correct_count = sum(1 for row in scored_rows if row["correct"])
    answered = sum(1 for row in scored_rows if row["prediction"] is not None)
    errors = sum(1 for row in scored_rows if row["error"] is not None)
    score: dict[str, Any] = {
        "protocol": "first-score-after-prediction-seal",
        "task": payload.get("task"),
        "metadata": payload.get("metadata", {}),
        "prediction_sha256": actual,
        "n": n,
        "correct": correct_count,
        "answered": answered,
        "errors": errors,
        "accuracy": correct_count / n if n else 0.0,
        "coverage": answered / n if n else 0.0,
        "selective_accuracy": correct_count / answered if answered else 0.0,
        "rows": scored_rows,
    }
    score_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.write_bytes(canonical_json_bytes(score))
    return score


def write_sha256_manifest(output_dir: Path) -> dict[str, str]:
    manifest_path = output_dir / "SHA256.json"
    manifest: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        manifest[path.relative_to(output_dir).as_posix()] = sha256_file(path)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest
