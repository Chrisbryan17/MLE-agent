from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.universal_core.holonomy_v2_2 import training_eval


def write_task(path: Path, target: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "train": [{"input": [[0]], "output": [[target]]}],
                "test": [{"input": [[0]], "output": [[target]]}],
            }
        ),
        encoding="utf-8",
    )


def build_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    write_task(vendor / "arc_agi_2" / "data" / "training" / "b.json", 2)
    write_task(vendor / "arc_agi_2" / "data" / "training" / "a.json", 1)
    return vendor


def test_training_run_is_ordered_and_keeps_test_targets_outside_core(tmp_path: Path, monkeypatch: Any) -> None:
    vendor = build_vendor(tmp_path)
    captured: list[dict[str, object]] = []

    def fake_run(task: dict[str, object], engine: object) -> dict[str, object]:
        captured.append(task)
        expected = 1 if task["task_id"] == "a" else 2
        return {
            "task_id": task["task_id"],
            "predictions": [{"status": "ACCEPTED", "prediction": [[expected]]}],
        }

    monkeypatch.setattr(training_eval, "run_public_task_v2_2", fake_run)

    report = training_eval.run_training_corpus(
        vendor,
        engine=object(),
        run_label="training-0001",
        candidate_commit="candidate-sha",
    )

    assert [item["task_id"] for item in report["reports"]] == ["a", "b"]
    assert report["metrics"]["correct"] == 2
    assert report["metrics"]["coverage"] == 1.0
    assert report["status_counts"] == {"ACCEPTED": 2}
    assert report["identity"]["candidate_commit"] == "candidate-sha"
    assert len(report["report_digest"]) == 64
    assert [item["hidden_inputs"] for item in captured] == [([[0]],), ([[0]],)]
    assert all("output" not in item for item in captured)


def test_training_run_counts_core_exception_as_failed_row(tmp_path: Path, monkeypatch: Any) -> None:
    vendor = build_vendor(tmp_path)

    def fail(task: object, engine: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(training_eval, "run_public_task_v2_2", fail)

    report = training_eval.run_training_corpus(vendor, engine=object(), run_label="training-failure")

    assert report["metrics"]["rows"] == 2
    assert report["metrics"]["failed"] == 2
    assert report["status_counts"] == {"RUNNER_FAILED": 2}
    assert all(item["error_type"] == "RuntimeError" for item in report["reports"])


def test_write_report_emits_canonical_json(tmp_path: Path) -> None:
    report = {"report_digest": "a" * 64, "metrics": {"rows": 0}}
    path = training_eval.write_report(report, tmp_path / "nested" / "report.json")

    assert path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(path.read_text(encoding="utf-8")) == report
