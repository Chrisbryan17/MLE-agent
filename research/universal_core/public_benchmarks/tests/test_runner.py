from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.public_benchmarks import runner


class DummyEngine:
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def build_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    write_json(
        vendor / "SNAPSHOT_MANIFEST.json",
        {"inventory_digest": runner.SNAPSHOT_INVENTORY_DIGEST},
    )
    for task_id in ("arc-a", "arc-b"):
        write_json(
            vendor / "arc_agi_2" / "data" / "evaluation" / f"{task_id}.json",
            {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [{"input": [[2]], "output": [[3]]}],
            },
        )
    for family in ("bbeh-a", "bbeh-b"):
        write_json(
            vendor / "bbeh" / "full" / family / "task.json",
            {
                "examples": [
                    {"input": "p0", "target": "A"},
                    {"input": "p1", "target": "B"},
                    {"input": "p2", "target": "C"},
                ]
            },
        )
    write_jsonl(
        vendor / "livebench" / "questions" / "reasoning.jsonl",
        [
            {"question_id": "q0", "category": "reasoning", "task": "spatial", "turns": ["p0"], "ground_truth": "A"},
            {"question_id": "q1", "category": "reasoning", "task": "spatial", "turns": ["p1"], "ground_truth": "B"},
            {"question_id": "q2", "category": "reasoning", "task": "zebra", "turns": ["p2"], "ground_truth": "C"},
            {"question_id": "q3", "category": "reasoning", "task": "zebra", "turns": ["p3"], "ground_truth": "D"},
        ],
    )
    write_jsonl(
        vendor / "livebench" / "questions" / "coding.jsonl",
        [{"question_id": "c0", "category": "coding", "task": "code", "turns": ["code"]}],
    )
    return vendor


def metrics(task_id: str, rows: int = 1) -> dict[str, object]:
    return {
        "task_id": task_id,
        "rows": rows,
        "correct": rows,
        "accepted": rows,
        "abstained": 0,
        "failed": 0,
        "incorrect_attempts": 0,
        "raw_accuracy": 1.0,
        "coverage": 1.0,
        "attempted_accuracy": 1.0,
    }


def test_smoke_runner_limits_each_benchmark_and_seals_report(tmp_path: Path, monkeypatch: Any) -> None:
    vendor = build_vendor(tmp_path)

    monkeypatch.setattr(
        runner.execution,
        "run_arc_payload",
        lambda task_id, payload, engine: {
            "task_id": task_id,
            "raw_result": {"task_id": task_id, "predictions": []},
            "submission": [{"attempt_1": [[3]], "attempt_2": [[3]]}],
            "metrics": metrics(task_id),
        },
    )
    monkeypatch.setattr(
        runner.execution,
        "run_bbeh_payload",
        lambda task_id, payload, engine, **kwargs: {
            "task_id": task_id,
            "raw_result": {"task_id": task_id, "predictions": []},
            "metrics": metrics(task_id),
        },
    )
    monkeypatch.setattr(
        runner.execution,
        "run_livebench_rows",
        lambda rows, engine, **kwargs: {
            "task_id": f"livebench:{rows[0]['category']}:{rows[0]['task']}",
            "raw_result": {"predictions": []},
            "metrics": metrics(f"livebench:{rows[0]['category']}:{rows[0]['task']}", len(rows) - 1),
        },
    )

    report = runner.run_public_benchmarks(
        vendor,
        DummyEngine(),
        mode="smoke",
        run_label="public-smoke-0001",
        bbeh_demonstrations=1,
        livebench_demonstrations=1,
    )

    assert report["identity"]["frozen_core_commit"] == runner.FROZEN_CORE_COMMIT
    assert report["identity"]["snapshot_inventory_digest"] == runner.SNAPSHOT_INVENTORY_DIGEST
    assert report["arc_agi_2"]["evaluated_tasks"] == 1
    assert report["bbeh_transfer"]["evaluated_families"] == 1
    assert report["livebench_scalar_transfer"]["evaluated_families"] == 1
    assert report["livebench_scalar_transfer"]["unsupported_rows"] == {"coding": 1}
    assert list(report["arc_agi_2"]["submission"]) == ["arc-a"]
    assert len(report["report_digest"]) == 64


def test_runner_converts_family_exception_to_failed_metrics(tmp_path: Path, monkeypatch: Any) -> None:
    vendor = build_vendor(tmp_path)
    monkeypatch.setattr(runner.execution, "run_arc_payload", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(runner.execution, "run_bbeh_payload", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(runner.execution, "run_livebench_rows", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    report = runner.run_public_benchmarks(vendor, DummyEngine(), mode="smoke", run_label="failure-smoke")

    assert report["arc_agi_2"]["metrics"]["failed"] == 1
    assert report["bbeh_transfer"]["metrics"]["failed"] == 1
    assert report["livebench_scalar_transfer"]["metrics"]["failed"] == 1
    assert report["arc_agi_2"]["reports"][0]["error_type"] == "RuntimeError"


def test_runner_rejects_wrong_snapshot_identity(tmp_path: Path) -> None:
    vendor = build_vendor(tmp_path)
    write_json(vendor / "SNAPSHOT_MANIFEST.json", {"inventory_digest": "wrong"})
    with pytest.raises(ValueError, match="snapshot inventory"):
        runner.run_public_benchmarks(vendor, DummyEngine(), mode="smoke", run_label="bad")


def test_write_outputs_emits_report_submission_and_checksums(tmp_path: Path) -> None:
    report = {
        "report_digest": "a" * 64,
        "arc_agi_2": {"submission": {"arc-a": [{"attempt_1": [[1]], "attempt_2": [[1]]}]}},
    }
    output = tmp_path / "out"

    paths = runner.write_outputs(report, output)

    assert json.loads((output / "report.json").read_text(encoding="utf-8")) == report
    assert json.loads((output / "arc_submission.json").read_text(encoding="utf-8")) == report["arc_agi_2"]["submission"]
    checksums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert "report.json" in checksums
    assert "arc_submission.json" in checksums
    assert set(paths) == {"report", "arc_submission", "checksums"}
