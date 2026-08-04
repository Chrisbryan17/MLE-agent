from __future__ import annotations

from research.universal_core.holonomy_v2_2.grid_induction import run_public_task_v2_2


def make_task(demos: list[dict[str, object]], hidden: list[object]) -> dict[str, object]:
    return {
        "task_id": "component-select",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def test_unique_largest_component_is_cropped() -> None:
    value = make_task(
        [{
            "input": [
                [0, 2, 0, 3, 3, 0],
                [0, 2, 0, 3, 3, 0],
                [0, 0, 0, 3, 0, 0],
            ],
            "output": [[3, 3], [3, 3], [3, 0]],
        }],
        [[
            [0, 4, 4, 0, 5, 5, 5],
            [0, 4, 0, 0, 5, 5, 5],
        ]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[5, 5, 5], [5, 5, 5]],
    }]
    assert "component_area_select" in result["evidence"]["candidate_kinds"]


def test_unique_smallest_component_is_cropped() -> None:
    value = make_task(
        [{
            "input": [
                [0, 2, 2, 2, 0, 7, 7],
                [0, 2, 2, 2, 0, 7, 7],
                [0, 2, 2, 2, 0, 0, 0],
            ],
            "output": [[7, 7], [7, 7]],
        }],
        [[
            [6, 6, 6, 0, 8],
            [6, 6, 6, 0, 8],
            [6, 6, 6, 0, 0],
        ]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[8], [8]],
    }]


def test_selected_component_crop_preserves_background_holes() -> None:
    value = make_task(
        [{
            "input": [
                [9, 4, 4, 4, 9, 2],
                [9, 4, 9, 4, 9, 2],
                [9, 4, 4, 4, 9, 9],
            ],
            "output": [[4, 4, 4], [4, 9, 4], [4, 4, 4]],
        }],
        [[
            [9, 3, 3, 3, 9, 6, 6],
            [9, 3, 9, 3, 9, 6, 9],
            [9, 3, 3, 3, 9, 9, 9],
        ]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[3, 3, 3], [3, 9, 3], [3, 3, 3]],
    }]


def test_hidden_area_tie_returns_execution_failure() -> None:
    value = make_task(
        [{
            "input": [[0, 2, 0, 3, 3], [0, 0, 0, 3, 0]],
            "output": [[3, 3], [3, 0]],
        }],
        [[[4, 4, 0, 5, 5]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "EXECUTION_FAILED", "prediction": None}]


def test_minimum_and_maximum_selectors_that_disagree_abstain() -> None:
    value = make_task(
        [{
            "input": [[0, 2, 2], [0, 2, 2]],
            "output": [[2, 2], [2, 2]],
        }],
        [[[3, 0, 4, 4], [0, 0, 4, 4]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "AMBIGUOUS_PROGRAM", "prediction": None}]
