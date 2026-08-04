from __future__ import annotations

from research.universal_core.holonomy_v2_2.grid_induction import run_public_task_v2_2


def make_task(demos: list[dict[str, object]], hidden: list[object]) -> dict[str, object]:
    return {
        "task_id": "panel-combine",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def test_vertical_panels_with_separator_use_intersection() -> None:
    value = make_task(
        [{
            "input": [[1, 0, 9, 2, 0], [1, 1, 9, 0, 2]],
            "output": [[4, 0], [0, 4]],
        }],
        [[[3, 3, 9, 5, 0], [0, 3, 9, 0, 5]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[4, 0], [0, 4]],
    }]
    assert "panel_boolean_combine" in result["evidence"]["candidate_kinds"]


def test_horizontal_panels_without_gap_use_exclusive_or() -> None:
    value = make_task(
        [{
            "input": [[1, 0], [0, 1], [0, 2], [2, 1]],
            "output": [[6, 6], [6, 0]],
        }],
        [[[3, 0], [3, 3], [0, 4], [4, 0]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[6, 6], [0, 6]],
    }]


def test_vertical_panels_can_select_left_only_cells() -> None:
    value = make_task(
        [{
            "input": [[1, 1, 0, 2], [0, 1, 2, 0]],
            "output": [[7, 0], [0, 7]],
        }],
        [[[3, 0, 0, 4], [3, 3, 4, 0]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[7, 0], [0, 7]],
    }]


def test_disagreeing_panel_rules_abstain() -> None:
    value = make_task(
        [{
            "input": [[1, 0, 0, 9, 0, 2, 0]],
            "output": [[5, 5, 0]],
        }],
        [[[1, 0, 0, 9, 2, 0, 0]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "AMBIGUOUS_PROGRAM", "prediction": None}]
