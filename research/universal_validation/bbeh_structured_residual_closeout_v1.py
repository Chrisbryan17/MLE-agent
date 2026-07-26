#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Callable, Sequence

import bbeh_zebra_exact_v1 as zebra

PINNED_BBEH_COMMIT = "80d12ca916b7158f22293fcf3144f4d3d854d4be"
TASK_NAME = "bbeh_zebra_puzzles"
ROOT = Path(os.environ.get("BBEH_TASK_ROOT", ".external/bbeh/bbeh/benchmark_tasks"))
OUT = Path(os.environ.get("STRUCTURED_RESIDUAL_OUT", "artifacts/structured_residual_v1"))


def _canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_predictions(
    examples: Sequence[dict[str, Any]],
    solver: Callable[[str], str | None],
    prediction_path: Path,
    seal_path: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, example in enumerate(examples):
        prompt = str(example["input"])
        started = time.perf_counter()
        try:
            prediction = solver(prompt)
            error = None
        except Exception as exc:  # Exceptions are recorded and score as wrong.
            prediction = None
            error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "index": index,
                "input_sha256": _sha256(prompt.encode("utf-8")),
                "prediction": None if prediction is None else str(prediction).strip(),
                "error": error,
                "latency_seconds": time.perf_counter() - started,
            }
        )

    payload = {
        "protocol": "targets-hidden-during-generation",
        "task": TASK_NAME,
        "pinned_bbeh_commit": PINNED_BBEH_COMMIT,
        "rows": rows,
    }
    raw = _canonical_json_bytes(payload)
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_bytes(raw)
    digest = _sha256(raw)
    seal_path.write_text(digest + "\n", encoding="utf-8")
    return payload


def score_predictions(
    examples: Sequence[dict[str, Any]],
    prediction_path: Path,
    seal_path: Path,
    score_path: Path,
) -> dict[str, Any]:
    raw = prediction_path.read_bytes()
    expected = seal_path.read_text(encoding="utf-8").strip()
    actual = _sha256(raw)
    if actual != expected:
        raise ValueError(f"prediction seal mismatch: expected {expected}, got {actual}")

    payload = json.loads(raw)
    rows = payload["rows"]
    if len(rows) != len(examples):
        raise ValueError(f"prediction/example length mismatch: {len(rows)} != {len(examples)}")

    scored_rows: list[dict[str, Any]] = []
    for index, (example, row) in enumerate(zip(examples, rows)):
        prompt = str(example["input"])
        prompt_hash = _sha256(prompt.encode("utf-8"))
        if row["index"] != index or row["input_sha256"] != prompt_hash:
            raise ValueError(f"prediction/input mismatch at index {index}")
        prediction = row.get("prediction")
        target = str(example["target"]).strip()
        correct = prediction is not None and str(prediction).strip() == target
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
    correct = sum(row["correct"] for row in scored_rows)
    answered = sum(row["prediction"] is not None for row in scored_rows)
    errors = sum(row["error"] is not None for row in scored_rows)
    score = {
        "protocol": "first-score-after-prediction-seal",
        "task": TASK_NAME,
        "pinned_bbeh_commit": PINNED_BBEH_COMMIT,
        "prediction_sha256": actual,
        "n": n,
        "correct": correct,
        "answered": answered,
        "errors": errors,
        "accuracy": correct / n if n else 0.0,
        "coverage": answered / n if n else 0.0,
        "selective_accuracy": correct / answered if answered else 0.0,
        "rows": scored_rows,
    }
    score_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.write_bytes(_canonical_json_bytes(score))
    return score


def main() -> None:
    task_path = ROOT / TASK_NAME / "task.json"
    examples = json.loads(task_path.read_text(encoding="utf-8"))["examples"]
    OUT.mkdir(parents=True, exist_ok=True)
    prediction_path = OUT / "predictions.json"
    seal_path = OUT / "predictions.sha256"
    score_path = OUT / "first_score.json"

    generated = generate_predictions(examples, zebra.solve, prediction_path, seal_path)
    score = score_predictions(examples, prediction_path, seal_path, score_path)
    error_families: dict[str, int] = {}
    for row in generated["rows"]:
        error = row.get("error")
        if error:
            family = error.split(":", 1)[0]
            error_families[family] = error_families.get(family, 0) + 1

    report = {
        "claims_boundary": (
            "Adaptive exact-compiler development on the pinned public BBEH corpus; "
            "not an unseen-test estimate. Exceptions and abstentions count wrong."
        ),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_path": str(task_path),
        "task_sha256": _sha256(task_path.read_bytes()),
        "prediction_sha256": score["prediction_sha256"],
        "score_sha256": _sha256(score_path.read_bytes()),
        "summary": {key: score[key] for key in ("n", "correct", "answered", "errors", "accuracy", "coverage", "selective_accuracy")},
        "error_families": error_families,
    }
    (OUT / "results.json").write_bytes(_canonical_json_bytes(report))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
