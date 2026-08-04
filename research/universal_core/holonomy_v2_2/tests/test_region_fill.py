from __future__ import annotations

from research.universal_core.holonomy_v2_2.grid_induction import run_public_task_v2_2


def make_task(demos: list[dict[str, object]], hidden: list[object]) -> dict[str, object]:
    return {
        "task_id": "region-fill",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def test_enclosed_background_cells_are_filled_on_a_copy() -> None:
    value = make_task(
        [{
            "input": [[0, 2, 2, 2, 0], [0, 2, 0, 2, 0], [0, 2, 2, 2, 0]],
            "output": [[0, 2, 2, 2, 0], [0, 2, 4, 2, 0], [0, 2, 2, 2, 0]],
        }],
        [[[3, 3, 3], [3, 0, 3], [3, 3, 3]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[3, 3, 3], [3, 4, 3], [3, 3, 3]],
    }]
    assert "enclosed_region_fill" in result["evidence"]["candidate_kinds"]


def test_only_enclosed_cells_can_be_highlighted() -> None:
    value = make_task(
        [{
            "input": [[0, 2, 2, 2, 0], [0, 2, 0, 2, 0], [0, 2, 2, 2, 0]],
            "output": [[0, 0, 0, 0, 0], [0, 0, 7, 0, 0], [0, 0, 0, 0, 0]],
        }],
        [[[5, 5, 5], [5, 0, 5], [5, 5, 5]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[0, 0, 0], [0, 7, 0], [0, 0, 0]],
    }]


def test_closed_regions_can_be_solidified_to_one_color() -> None:
    value = make_task(
        [{
            "input": [[0, 2, 2, 2, 0], [0, 2, 0, 2, 0], [0, 2, 2, 2, 0]],
            "output": [[0, 6, 6, 6, 0], [0, 6, 6, 6, 0], [0, 6, 6, 6, 0]],
        }],
        [[[0, 3, 3, 0], [0, 3, 0, 3], [0, 3, 3, 3]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[0, 6, 6, 0], [0, 6, 6, 6], [0, 6, 6, 6]],
    }]


def test_background_connected_to_border_is_not_enclosed() -> None:
    value = make_task(
        [{
            "input": [[2, 2, 2], [2, 0, 0], [2, 2, 2]],
            "output": [[2, 2, 2], [2, 0, 0], [2, 2, 2]],
        }],
        [[[3, 3, 3], [3, 0, 3], [3, 3, 3]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "AMBIGUOUS_PROGRAM", "prediction": None}]
