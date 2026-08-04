from __future__ import annotations

import pytest

from research.universal_core.public_benchmarks.adapters.arc_agi_2 import (
    ARC_INSTRUCTIONS,
    accepted_grid,
    arc_task_from_payload,
    build_submission,
    validate_grid,
)


def test_arc_task_strips_test_targets_and_preserves_order() -> None:
    payload = {
        "train": [
            {"input": [[0, 1]], "output": [[1, 0]]},
            {"input": [[2], [3]], "output": [[3], [2]]},
        ],
        "test": [
            {"input": [[4, 5]], "output": [[5, 4]]},
            {"input": [[6]], "output": [[6]]},
        ],
    }

    task = arc_task_from_payload("task-a", payload)

    assert task == {
        "task_id": "task-a",
        "instructions": ARC_INSTRUCTIONS,
        "demonstrations": (
            {"input": [[0, 1]], "output": [[1, 0]]},
            {"input": [[2], [3]], "output": [[3], [2]]},
        ),
        "hidden_inputs": (
            [[4, 5]],
            [[6]],
        ),
    }


@pytest.mark.parametrize(
    "grid",
    [
        [],
        [[]],
        [[0], [0, 1]],
        [[-1]],
        [[10]],
        [[True]],
        [[0.0]],
        [[0] * 31],
        [[0] for _ in range(31)],
    ],
)
def test_validate_grid_rejects_invalid_arc_grids(grid: object) -> None:
    with pytest.raises(ValueError):
        validate_grid(grid)


def test_validate_grid_returns_detached_json_grid() -> None:
    source = [[0, 1], [2, 3]]
    grid = validate_grid(source)
    source[0][0] = 9
    assert grid == [[0, 1], [2, 3]]


def test_accepted_grid_requires_accepted_status_and_valid_shape() -> None:
    assert accepted_grid({"status": "ACCEPTED", "prediction": [[1, 2], [3, 4]]}) == [[1, 2], [3, 4]]
    assert accepted_grid({"status": "LOW_EVIDENCE", "prediction": [[1]]}) is None
    assert accepted_grid({"status": "ACCEPTED", "prediction": [[11]]}) is None
    assert accepted_grid({"status": "ACCEPTED", "prediction": "not-a-grid"}) is None


def test_build_submission_emits_two_attempts_for_each_prediction() -> None:
    task_results = [
        {
            "task_id": "task-a",
            "predictions": [
                {"status": "ACCEPTED", "prediction": [[1, 2]]},
                {"status": "LOW_EVIDENCE", "prediction": None},
            ],
        },
        {
            "task_id": "task-b",
            "predictions": [
                {"status": "ACCEPTED", "prediction": [[3], [4]]},
            ],
        },
    ]

    assert build_submission(task_results) == {
        "task-a": [
            {"attempt_1": [[1, 2]], "attempt_2": [[1, 2]]},
            {"attempt_1": [[0]], "attempt_2": [[0]]},
        ],
        "task-b": [
            {"attempt_1": [[3], [4]], "attempt_2": [[3], [4]]},
        ],
    }


def test_build_submission_rejects_duplicate_task_ids() -> None:
    with pytest.raises(ValueError, match="duplicate ARC task id"):
        build_submission(
            [
                {"task_id": "same", "predictions": []},
                {"task_id": "same", "predictions": []},
            ]
        )
