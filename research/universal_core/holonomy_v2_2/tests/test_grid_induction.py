from __future__ import annotations

from typing import Any

from research.universal_core.holonomy_v2_2 import grid_induction


def task(demos: list[dict[str, object]], hidden: list[object], task_id: str = "grid-task") -> dict[str, object]:
    return {
        "task_id": task_id,
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def test_color_map_is_inferred_across_all_demonstrations() -> None:
    value = task(
        [
            {"input": [[0, 1], [1, 0]], "output": [[2, 3], [3, 2]]},
            {"input": [[1, 0]], "output": [[3, 2]]},
        ],
        [[[0, 1, 0]]],
    )

    result = grid_induction.run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "ACCEPTED", "prediction": [[2, 3, 2]]}]
    assert result["program_digest"] is not None


def test_rotation_and_reflection_candidates_predict_hidden_grids() -> None:
    rotation = task(
        [{"input": [[1, 2], [3, 4]], "output": [[3, 1], [4, 2]]}],
        [[[5, 6], [7, 8]]],
        "rotate",
    )
    reflection = task(
        [{"input": [[1, 2, 3], [4, 5, 6]], "output": [[3, 2, 1], [6, 5, 4]]}],
        [[[7, 8], [9, 0]]],
        "reflect",
    )

    rotated = grid_induction.run_public_task_v2_2(rotation, engine=None)
    reflected = grid_induction.run_public_task_v2_2(reflection, engine=None)

    assert rotated["predictions"][0] == {"status": "ACCEPTED", "prediction": [[7, 5], [8, 6]]}
    assert reflected["predictions"][0] == {"status": "ACCEPTED", "prediction": [[8, 7], [0, 9]]}


def test_cell_scale_and_whole_grid_tile_are_distinct() -> None:
    scale = task(
        [{"input": [[1, 2]], "output": [[1, 1, 2, 2], [1, 1, 2, 2]]}],
        [[[3], [4]]],
        "scale",
    )
    tile = task(
        [{"input": [[1, 2]], "output": [[1, 2, 1, 2], [1, 2, 1, 2]]}],
        [[[3], [4]]],
        "tile",
    )

    scaled = grid_induction.run_public_task_v2_2(scale, engine=None)
    tiled = grid_induction.run_public_task_v2_2(tile, engine=None)

    assert scaled["predictions"][0]["prediction"] == [[3, 3], [3, 3], [4, 4], [4, 4]]
    assert tiled["predictions"][0]["prediction"] == [[3, 3], [4, 4], [3, 3], [4, 4]]


def test_crop_uses_a_demonstrated_background_value() -> None:
    value = task(
        [
            {
                "input": [[0, 0, 0, 0], [0, 4, 4, 0], [0, 0, 0, 0]],
                "output": [[4, 4]],
            },
            {
                "input": [[0, 5, 0], [0, 5, 0], [0, 0, 0]],
                "output": [[5], [5]],
            },
        ],
        [[[0, 0, 0], [6, 6, 0], [0, 0, 0]]],
    )

    result = grid_induction.run_public_task_v2_2(value, engine=None)

    assert result["predictions"] == [{"status": "ACCEPTED", "prediction": [[6, 6]]}]


def test_distinct_hidden_outputs_from_fitting_programs_abstain() -> None:
    value = task(
        [{"input": [[1, 1], [1, 1]], "output": [[1, 1], [1, 1]]}],
        [[[1, 2], [3, 4]]],
    )

    result = grid_induction.run_public_task_v2_2(value, engine=None)

    assert result["program_digest"] is None
    assert result["predictions"] == [{"status": "AMBIGUOUS_PROGRAM", "prediction": None}]


def test_no_fitting_grid_program_returns_grammar_exhausted() -> None:
    value = task(
        [{"input": [[1, 2], [3, 4]], "output": [[9, 9, 9], [9, 9, 9], [9, 9, 9]]}],
        [[[5]]],
    )

    result = grid_induction.run_public_task_v2_2(value, engine=None)

    assert result["program_digest"] is None
    assert result["predictions"] == [{"status": "GRAMMAR_EXHAUSTED", "prediction": None}]


def test_program_identity_does_not_depend_on_task_id() -> None:
    demos = [{"input": [[1, 2]], "output": [[2, 1]]}]
    first = grid_induction.run_public_task_v2_2(task(demos, [[[3, 4]]], "first"), engine=None)
    second = grid_induction.run_public_task_v2_2(task(demos, [[[3, 4]]], "second"), engine=None)

    assert first["program_digest"] == second["program_digest"]
    assert first["freeze_digest"] == second["freeze_digest"]


def test_non_grid_task_delegates_to_frozen_v2(monkeypatch: Any) -> None:
    expected = {"task_id": "text", "predictions": [{"status": "ACCEPTED", "prediction": "B"}]}
    calls: list[tuple[object, object]] = []

    def fake_delegate(value: object, engine: object) -> dict[str, object]:
        calls.append((value, engine))
        return expected

    monkeypatch.setattr(grid_induction, "run_public_task_v2", fake_delegate)
    value = task([{"input": "A", "output": "B"}], ["A"], "text")
    marker = object()

    assert grid_induction.run_public_task_v2_2(value, marker) is expected
    assert calls == [(value, marker)]
