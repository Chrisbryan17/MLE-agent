from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from research.universal_core.public_benchmarks import suite
from research.universal_core.public_benchmarks.adapters.arc_agi_2 import (
    arc_task_from_payload,
    score_result,
)

from .grid_induction import run_public_task_v2_2


FROZEN_CORE_COMMIT = "1d7c489bcdbff755d638b35ad47ce62bd4fe829d"


def _failed_metrics(task_id: str, rows: int) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "rows": rows,
        "correct": 0,
        "accepted": 0,
        "abstained": 0,
        "failed": rows,
        "incorrect_attempts": 0,
        "raw_accuracy": 0.0,
        "coverage": 0.0,
        "attempted_accuracy": 0.0,
    }


def _failure_report(task_id: str, payload: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
    test_rows = payload.get("test")
    rows = len(test_rows) if isinstance(test_rows, (list, tuple)) else 0
    return {
        "task_id": task_id,
        "raw_result": {
            "task_id": task_id,
            "program_digest": None,
            "freeze_digest": None,
            "prediction_digest": None,
            "predictions": [
                {"status": "RUNNER_FAILED", "prediction": None}
                for _ in range(rows)
            ],
        },
        "metrics": _failed_metrics(task_id, rows),
        "error_type": type(exc).__name__,
    }


def _status_counts(reports: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for report in reports:
        raw = report.get("raw_result")
        predictions = raw.get("predictions") if isinstance(raw, Mapping) else None
        if not isinstance(predictions, (list, tuple)):
            continue
        for item in predictions:
            status = item.get("status") if isinstance(item, Mapping) else "RUNNER_FAILED"
            name = str(status)
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def run_training_corpus(
    vendor: Path | str,
    engine: Any,
    *,
    run_label: str,
    candidate_commit: str | None = None,
) -> dict[str, Any]:
    if not isinstance(run_label, str) or not run_label:
        raise ValueError("run label must be a non-empty string")
    tasks = suite.load_arc_tasks(Path(vendor), "training")
    reports: list[dict[str, Any]] = []
    for task_id, payload in tasks:
        public_task = arc_task_from_payload(task_id, payload)
        try:
            raw_result = run_public_task_v2_2(public_task, engine)
            report = {
                "task_id": task_id,
                "raw_result": raw_result,
                "metrics": score_result(task_id, payload, raw_result),
            }
        except Exception as exc:
            report = _failure_report(task_id, payload, exc)
        reports.append(report)

    body = {
        "schema_version": 1,
        "run_label": run_label,
        "split": "training",
        "identity": {
            "candidate_commit": candidate_commit,
            "frozen_core_commit": FROZEN_CORE_COMMIT,
        },
        "evaluated_tasks": len(reports),
        "metrics": suite.aggregate_metrics(item["metrics"] for item in reports),
        "status_counts": _status_counts(reports),
        "reports": reports,
    }
    return suite.seal_report(body)


def write_report(report: Mapping[str, Any], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
