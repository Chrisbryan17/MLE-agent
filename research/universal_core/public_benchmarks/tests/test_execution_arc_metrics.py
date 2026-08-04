from __future__ import annotations

from typing import Any

from research.universal_core.public_benchmarks.adapters import execution


class DummyEngine:
    pass


def test_arc_execution_includes_exact_public_metrics(monkeypatch: Any) -> None:
    def fake_run(task: dict[str, Any], engine: object) -> dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "predictions": [
                {"status": "ACCEPTED", "prediction": [[2, 1]]},
                {"status": "LOW_EVIDENCE", "prediction": None},
            ],
        }

    monkeypatch.setattr(execution, "run_public_task_v2", fake_run)
    payload = {
        "train": [{"input": [[0, 1]], "output": [[1, 0]]}],
        "test": [
            {"input": [[1, 2]], "output": [[2, 1]]},
            {"input": [[3]], "output": [[3]]},
        ],
    }

    report = execution.run_arc_payload("arc-a", payload, DummyEngine())

    assert report["metrics"] == {
        "task_id": "arc-a",
        "rows": 2,
        "correct": 1,
        "accepted": 1,
        "abstained": 1,
        "failed": 0,
        "incorrect_attempts": 0,
        "raw_accuracy": 0.5,
        "coverage": 0.5,
        "attempted_accuracy": 1.0,
    }
