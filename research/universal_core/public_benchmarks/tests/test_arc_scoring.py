from __future__ import annotations

import pytest

from research.universal_core.public_benchmarks.adapters.arc_agi_2 import score_result


def payload() -> dict[str, object]:
    return {
        "train": [{"input": [[0]], "output": [[1]]}],
        "test": [
            {"input": [[1, 2]], "output": [[2, 1]]},
            {"input": [[3]], "output": [[3]]},
            {"input": [[4]], "output": [[5]]},
            {"input": [[6]], "output": [[6]]},
        ],
    }


def test_arc_scoring_reports_exact_grid_metrics() -> None:
    result = {
        "task_id": "arc-a",
        "predictions": [
            {"status": "ACCEPTED", "prediction": [[2, 1]]},
            {"status": "ACCEPTED", "prediction": [[0]]},
            {"status": "LOW_EVIDENCE", "prediction": None},
            {"status": "EXECUTION_FAILED", "prediction": None},
        ],
    }

    assert score_result("arc-a", payload(), result) == {
        "task_id": "arc-a",
        "rows": 4,
        "correct": 1,
        "accepted": 2,
        "abstained": 1,
        "failed": 1,
        "incorrect_attempts": 1,
        "raw_accuracy": 0.25,
        "coverage": 0.5,
        "attempted_accuracy": 0.5,
    }


def test_arc_scoring_rejects_missing_public_targets() -> None:
    missing = {
        "train": [{"input": [[0]], "output": [[1]]}],
        "test": [{"input": [[1]]}],
    }
    with pytest.raises(ValueError, match="public target"):
        score_result("arc-a", missing, {"task_id": "arc-a", "predictions": []})


def test_arc_scoring_rejects_prediction_count_mismatch() -> None:
    with pytest.raises(ValueError, match="prediction count"):
        score_result("arc-a", payload(), {"task_id": "arc-a", "predictions": []})
