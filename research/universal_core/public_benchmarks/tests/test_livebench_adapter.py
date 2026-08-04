from __future__ import annotations

import pytest

from research.universal_core.public_benchmarks.adapters.livebench import (
    LIVEBENCH_INSTRUCTIONS,
    livebench_task_from_rows,
    score_result,
)


def rows() -> list[dict[str, object]]:
    return [
        {
            "question_id": "q0",
            "category": "reasoning",
            "task": "spatial",
            "turns": ["prompt 0"],
            "ground_truth": "A",
        },
        {
            "question_id": "q1",
            "category": "reasoning",
            "task": "spatial",
            "turns": ["prompt 1"],
            "ground_truth": "B",
        },
        {
            "question_id": "q2",
            "category": "reasoning",
            "task": "spatial",
            "turns": ["prompt 2"],
            "ground_truth": "C",
        },
        {
            "question_id": "q3",
            "category": "reasoning",
            "task": "spatial",
            "turns": ["prompt 3"],
            "ground_truth": "D",
        },
    ]


def test_livebench_task_keeps_targets_and_ids_outside_public_task() -> None:
    prepared = livebench_task_from_rows(rows(), demonstration_count=2)

    assert prepared.task == {
        "task_id": "livebench:reasoning:spatial",
        "instructions": LIVEBENCH_INSTRUCTIONS,
        "demonstrations": (
            {"input": "prompt 0", "output": "A"},
            {"input": "prompt 1", "output": "B"},
        ),
        "hidden_inputs": ("prompt 2", "prompt 3"),
    }
    assert prepared.targets == ("C", "D")
    assert prepared.question_ids == ("q2", "q3")
    assert prepared.category == "reasoning"
    assert prepared.family == "spatial"


def test_livebench_task_supports_deterministic_rotation() -> None:
    prepared = livebench_task_from_rows(rows(), demonstration_count=1, offset=3)

    assert prepared.task["demonstrations"] == ({"input": "prompt 3", "output": "D"},)
    assert prepared.task["hidden_inputs"] == ("prompt 0", "prompt 1", "prompt 2")
    assert prepared.targets == ("A", "B", "C")
    assert prepared.question_ids == ("q0", "q1", "q2")


@pytest.mark.parametrize("category", ["coding", "instruction_following"])
def test_livebench_task_rejects_rows_without_scalar_targets(category: str) -> None:
    unsupported = [
        {
            "question_id": "q0",
            "category": category,
            "task": "family",
            "turns": ["prompt"],
        },
        {
            "question_id": "q1",
            "category": category,
            "task": "family",
            "turns": ["prompt 2"],
        },
    ]
    with pytest.raises(ValueError, match="deterministic string target"):
        livebench_task_from_rows(unsupported, demonstration_count=1)


def test_livebench_task_rejects_mixed_families() -> None:
    mixed = rows()
    mixed[-1] = {**mixed[-1], "task": "zebra_puzzle"}
    with pytest.raises(ValueError, match="same category and task family"):
        livebench_task_from_rows(mixed, demonstration_count=1)


def test_livebench_task_rejects_multi_turn_rows() -> None:
    invalid = rows()
    invalid[0] = {**invalid[0], "turns": ["first", "second"]}
    with pytest.raises(ValueError, match="exactly one turn"):
        livebench_task_from_rows(invalid, demonstration_count=1)


def test_livebench_scoring_reports_coverage_and_failures() -> None:
    prepared = livebench_task_from_rows(rows(), demonstration_count=1)
    result = {
        "task_id": "livebench:reasoning:spatial",
        "predictions": [
            {"status": "ACCEPTED", "prediction": "B"},
            {"status": "EXECUTION_FAILED", "prediction": None},
            {"status": "LOW_EVIDENCE", "prediction": None},
        ],
    }

    assert score_result(prepared, result) == {
        "task_id": "livebench:reasoning:spatial",
        "category": "reasoning",
        "family": "spatial",
        "rows": 3,
        "correct": 1,
        "accepted": 1,
        "abstained": 1,
        "failed": 1,
        "incorrect_attempts": 0,
        "raw_accuracy": 1 / 3,
        "coverage": 1 / 3,
        "attempted_accuracy": 1.0,
    }


def test_livebench_scoring_rejects_prediction_count_mismatch() -> None:
    prepared = livebench_task_from_rows(rows(), demonstration_count=1)
    with pytest.raises(ValueError, match="prediction count"):
        score_result(prepared, {"task_id": prepared.task["task_id"], "predictions": []})
