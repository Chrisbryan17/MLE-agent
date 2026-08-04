from __future__ import annotations

from typing import Any

from research.universal_core.public_benchmarks.adapters import execution


class DummyEngine:
    pass


def test_arc_execution_strips_targets_and_builds_submission(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(task: dict[str, Any], engine: object) -> dict[str, Any]:
        captured.update(task)
        assert isinstance(engine, DummyEngine)
        return {
            "task_id": task["task_id"],
            "predictions": [{"status": "ACCEPTED", "prediction": [[2, 1]]}],
            "program_digest": "program",
        }

    monkeypatch.setattr(execution, "run_public_task_v2", fake_run)
    payload = {
        "train": [{"input": [[0, 1]], "output": [[1, 0]]}],
        "test": [{"input": [[1, 2]], "output": [[2, 1]]}],
    }

    report = execution.run_arc_payload("arc-a", payload, DummyEngine())

    assert captured["hidden_inputs"] == ([[1, 2]],)
    assert "output" not in captured["hidden_inputs"][0]
    assert report["raw_result"]["program_digest"] == "program"
    assert report["submission"] == [
        {"attempt_1": [[2, 1]], "attempt_2": [[2, 1]]},
    ]


def test_bbeh_execution_keeps_hidden_targets_outside_engine(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(task: dict[str, Any], engine: object) -> dict[str, Any]:
        captured.update(task)
        return {
            "task_id": task["task_id"],
            "predictions": [
                {"status": "ACCEPTED", "prediction": "C"},
                {"status": "LOW_EVIDENCE", "prediction": None},
            ],
        }

    monkeypatch.setattr(execution, "run_public_task_v2", fake_run)
    payload = {
        "examples": [
            {"input": "p0", "target": "A"},
            {"input": "p1", "target": "B"},
            {"input": "p2", "target": "C"},
            {"input": "p3", "target": "D"},
        ]
    }

    report = execution.run_bbeh_payload(
        "bbeh-demo",
        payload,
        DummyEngine(),
        demonstration_count=2,
    )

    assert captured["hidden_inputs"] == ("p2", "p3")
    assert all("target" not in item for item in captured["demonstrations"])
    assert report["hidden_example_indices"] == [2, 3]
    assert report["metrics"]["correct"] == 1
    assert report["metrics"]["coverage"] == 0.5


def test_livebench_execution_keeps_targets_and_ids_outside_engine(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(task: dict[str, Any], engine: object) -> dict[str, Any]:
        captured.update(task)
        return {
            "task_id": task["task_id"],
            "predictions": [
                {"status": "ACCEPTED", "prediction": "B"},
                {"status": "EXECUTION_FAILED", "prediction": None},
            ],
        }

    monkeypatch.setattr(execution, "run_public_task_v2", fake_run)
    rows = [
        {"question_id": "q0", "category": "reasoning", "task": "spatial", "turns": ["p0"], "ground_truth": "A"},
        {"question_id": "q1", "category": "reasoning", "task": "spatial", "turns": ["p1"], "ground_truth": "B"},
        {"question_id": "q2", "category": "reasoning", "task": "spatial", "turns": ["p2"], "ground_truth": "C"},
    ]

    report = execution.run_livebench_rows(rows, DummyEngine(), demonstration_count=1)

    assert captured["hidden_inputs"] == ("p1", "p2")
    assert "question_id" not in captured
    assert report["hidden_question_ids"] == ["q1", "q2"]
    assert report["metrics"]["correct"] == 1
    assert report["metrics"]["failed"] == 1
