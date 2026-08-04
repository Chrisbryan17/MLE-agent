from __future__ import annotations

import pytest

from research.universal_core.public_benchmarks.adapters.bbeh import (
    BBEH_INSTRUCTIONS,
    bbeh_task_from_payload,
    score_result,
)


def payload() -> dict[str, object]:
    return {
        "canary": "ignore this field",
        "examples": [
            {"input": "question 0", "target": "A"},
            {"input": "question 1", "target": "B"},
            {"input": "question 2", "target": "C"},
            {"input": "question 3", "target": "D"},
            {"input": "question 4", "target": "E"},
        ],
    }


def test_bbeh_task_keeps_hidden_targets_outside_public_task() -> None:
    prepared = bbeh_task_from_payload("bbeh_demo", payload(), demonstration_count=2)

    assert prepared.task == {
        "task_id": "bbeh_demo",
        "instructions": BBEH_INSTRUCTIONS,
        "demonstrations": (
            {"input": "question 0", "output": "A"},
            {"input": "question 1", "output": "B"},
        ),
        "hidden_inputs": ("question 2", "question 3", "question 4"),
    }
    assert prepared.targets == ("C", "D", "E")
    assert prepared.example_indices == (2, 3, 4)


def test_bbeh_task_supports_deterministic_rotated_split() -> None:
    prepared = bbeh_task_from_payload(
        "bbeh_demo",
        payload(),
        demonstration_count=2,
        offset=3,
    )

    assert prepared.task["demonstrations"] == (
        {"input": "question 3", "output": "D"},
        {"input": "question 4", "output": "E"},
    )
    assert prepared.task["hidden_inputs"] == ("question 0", "question 1", "question 2")
    assert prepared.targets == ("A", "B", "C")
    assert prepared.example_indices == (0, 1, 2)


@pytest.mark.parametrize("demonstration_count", [0, 5, 6])
def test_bbeh_task_requires_demo_and_hidden_rows(demonstration_count: int) -> None:
    with pytest.raises(ValueError):
        bbeh_task_from_payload(
            "bbeh_demo",
            payload(),
            demonstration_count=demonstration_count,
        )


def test_bbeh_task_rejects_invalid_examples() -> None:
    with pytest.raises(ValueError):
        bbeh_task_from_payload(
            "bad",
            {"examples": [{"input": "question", "target": ""}, {"input": "next", "target": "A"}]},
            demonstration_count=1,
        )


def test_bbeh_scoring_reports_raw_and_attempted_metrics() -> None:
    prepared = bbeh_task_from_payload("bbeh_demo", payload(), demonstration_count=2)
    result = {
        "task_id": "bbeh_demo",
        "predictions": [
            {"status": "ACCEPTED", "prediction": "C"},
            {"status": "LOW_EVIDENCE", "prediction": None},
            {"status": "ACCEPTED", "prediction": "wrong"},
        ],
    }

    assert score_result(prepared, result) == {
        "task_id": "bbeh_demo",
        "rows": 3,
        "correct": 1,
        "accepted": 2,
        "abstained": 1,
        "failed": 0,
        "incorrect_attempts": 1,
        "raw_accuracy": 1 / 3,
        "coverage": 2 / 3,
        "attempted_accuracy": 1 / 2,
    }


def test_bbeh_scoring_rejects_prediction_count_mismatch() -> None:
    prepared = bbeh_task_from_payload("bbeh_demo", payload(), demonstration_count=2)
    with pytest.raises(ValueError, match="prediction count"):
        score_result(prepared, {"task_id": "bbeh_demo", "predictions": []})
