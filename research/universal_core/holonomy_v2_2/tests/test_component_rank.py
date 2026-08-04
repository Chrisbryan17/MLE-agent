from __future__ import annotations

from research.universal_core.holonomy_v2_2.grid_induction import run_public_task_v2_2


def make_task(demos: list[dict[str, object]], hidden: list[object]) -> dict[str, object]:
    return {
        "task_id": "component-rank",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def test_components_use_ascending_size_rank_colors() -> None:
    value = make_task(
        [{
            "input": [[5, 0, 5, 0, 5], [0, 0, 5, 0, 5], [0, 0, 0, 0, 5]],
            "output": [[1, 0, 2, 0, 3], [0, 0, 2, 0, 3], [0, 0, 0, 0, 3]],
        }],
        [[[5, 0, 5, 0, 5], [5, 0, 5, 0, 0], [5, 0, 0, 0, 0]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{
        "status": "ACCEPTED",
        "prediction": [[3, 0, 2, 0, 1], [3, 0, 2, 0, 0], [3, 0, 0, 0, 0]],
    }]
    assert "component_rank_color" in result["evidence"]["candidate_kinds"]


def test_middle_size_class_can_map_to_background() -> None:
    value = make_task(
        [{
            "input": [[4, 0, 4, 0, 4], [0, 0, 4, 0, 4], [0, 0, 0, 0, 4]],
            "output": [[1, 0, 0, 0, 2], [0, 0, 0, 0, 2], [0, 0, 0, 0, 2]],
        }],
        [[[4, 0, 4, 4, 0], [4, 0, 0, 0, 0], [4, 0, 4, 4, 4]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"][0] == {
        "status": "ACCEPTED",
        "prediction": [[0, 0, 1, 1, 0], [0, 0, 0, 0, 0], [0, 0, 2, 2, 2]],
    }


def test_unseen_size_rank_returns_execution_failure() -> None:
    value = make_task(
        [{
            "input": [[5, 0, 5], [0, 0, 5]],
            "output": [[1, 0, 2], [0, 0, 2]],
        }],
        [[[5, 0, 5, 0, 5], [0, 0, 5, 0, 5], [0, 0, 0, 0, 5]]],
    )

    result = run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "EXECUTION_FAILED", "prediction": None}]
