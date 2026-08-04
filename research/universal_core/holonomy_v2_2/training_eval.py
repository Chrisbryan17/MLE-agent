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
from .mechanistic_trace import validate_trace, write_trace
from .trace_diagnosis import build_trace_diagnosis, write_diagnosis


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


def _without_mechanistic_trace(result: Mapping[str, Any]) -> dict[str, Any]:
    compact = dict(result)
    compact.pop("mechanistic_trace", None)
    return compact


def _trace_reference(trace: Mapping[str, Any], filename: str) -> dict[str, Any]:
    return {
        "path": filename,
        "trace_digest": str(trace["trace_digest"]),
        "envelope_digest": str(trace["envelope_digest"]),
        "event_count": int(trace["event_count"]),
        "terminal_status": str(trace["terminal_status"]),
    }


def run_training_corpus(
    vendor: Path | str,
    engine: Any,
    *,
    run_label: str,
    candidate_commit: str | None = None,
    mechanistic_dir: Path | str | None = None,
    verify_parity: bool = False,
) -> dict[str, Any]:
    if not isinstance(run_label, str) or not run_label:
        raise ValueError("run label must be a non-empty string")
    if verify_parity and mechanistic_dir is None:
        raise ValueError("parity verification requires a mechanistic directory")

    trace_root = Path(mechanistic_dir) if mechanistic_dir is not None else None
    if trace_root is not None:
        trace_root.mkdir(parents=True, exist_ok=True)

    tasks = suite.load_arc_tasks(Path(vendor), "training")
    reports: list[dict[str, Any]] = []
    traces: list[Mapping[str, Any]] = []
    parity_count = 0

    for task_id, payload in tasks:
        public_task = arc_task_from_payload(task_id, payload)
        try:
            compact_result = run_public_task_v2_2(public_task, engine)
            report = {
                "task_id": task_id,
                "raw_result": compact_result,
                "metrics": score_result(task_id, payload, compact_result),
            }
        except Exception as exc:
            reports.append(_failure_report(task_id, payload, exc))
            continue

        if trace_root is not None:
            traced_result = run_public_task_v2_2(
                public_task,
                engine,
                mechanistic=True,
            )
            trace = traced_result.get("mechanistic_trace")
            if not isinstance(trace, Mapping):
                raise RuntimeError(f"missing mechanistic trace for task {task_id}")
            traced_compact = _without_mechanistic_trace(traced_result)
            if verify_parity:
                if traced_compact != compact_result:
                    raise RuntimeError(f"mechanistic parity failure for task {task_id}")
                parity_count += 1
            validate_trace(trace)
            filename = f"{task_id}.json"
            write_trace(trace, trace_root / filename)
            report["mechanistic_trace"] = _trace_reference(trace, filename)
            traces.append(trace)

        reports.append(report)

    body: dict[str, Any] = {
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

    if trace_root is not None:
        diagnosis = build_trace_diagnosis(traces)
        write_diagnosis(diagnosis, trace_root / "diagnosis.json")
        schemas = sorted({str(trace["schema"]) for trace in traces})
        body["mechanistic"] = {
            "trace_schema": schemas[0] if len(schemas) == 1 else schemas,
            "trace_count": len(traces),
            "parity_checked": verify_parity,
            "parity_count": parity_count,
            "diagnosis_path": "diagnosis.json",
            "diagnosis_digest": diagnosis["diagnosis_digest"],
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
