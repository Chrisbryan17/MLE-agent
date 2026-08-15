from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.ray_extend import (
    apply_ray_extend,
    ray_extend_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "ray_extend"
_TASK_IDS = ("623ea044", "d037b0a7")


def load_payload(task_id: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / f"{task_id}.json").read_text(encoding="utf-8"))


def public_task(task_id: str) -> dict[str, Any]:
    payload = load_payload(task_id)
    return {
        "task_id": task_id,
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": payload["train"],
        "hidden_inputs": [item["input"] for item in payload["test"]],
    }


def expected_predictions(task_id: str) -> list[dict[str, Any]]:
    return [
        {"status": "ACCEPTED", "prediction": item["output"]}
        for item in load_payload(task_id)["test"]
    ]


def test_down_ray_extends_each_anchor_to_bottom_border() -> None:
    assert apply_ray_extend(
        {"kind": "anchor_ray_extend", "background": 0, "mode": "down"},
        [[1, 0], [0, 2], [0, 0]],
    ) == [[1, 0], [1, 2], [1, 2]]


def test_diagonal_ray_extends_anchor_to_four_diagonal_borders() -> None:
    assert apply_ray_extend(
        {"kind": "anchor_ray_extend", "background": 0, "mode": "diagonal"},
        [[0, 0, 0], [0, 3, 0], [0, 0, 0]],
    ) == [[3, 0, 3], [0, 3, 0], [3, 0, 3]]


def test_orthogonal_ray_extends_anchor_in_four_cardinal_directions() -> None:
    assert apply_ray_extend(
        {"kind": "anchor_ray_extend", "background": 0, "mode": "orthogonal"},
        [[0, 0, 0], [0, 4, 0], [0, 0, 0]],
    ) == [[0, 4, 0], [4, 4, 4], [0, 4, 0]]


def test_ray_extension_preserves_original_anchor_cells() -> None:
    source = [[5, 0, 0], [0, 0, 0]]
    output = apply_ray_extend(
        {"kind": "anchor_ray_extend", "background": 0, "mode": "right"},
        source,
    )

    assert source == [[5, 0, 0], [0, 0, 0]]
    assert output == [[5, 5, 5], [0, 0, 0]]


def test_ray_extension_rejects_cross_color_conflict() -> None:
    with pytest.raises(ValueError, match="ray extension color conflict"):
        apply_ray_extend(
            {"kind": "anchor_ray_extend", "background": 0, "mode": "right"},
            [[1, 0, 2]],
        )


def test_ray_extension_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown ray extension mode"):
        apply_ray_extend(
            {"kind": "anchor_ray_extend", "background": 0, "mode": "spiral"},
            [[1, 0], [0, 0]],
        )


def test_program_derivation_returns_unique_down_candidate() -> None:
    source = [[1, 0], [0, 2], [0, 0]]
    target = [[1, 0], [1, 2], [1, 2]]

    programs, reason = ray_extend_programs(((source, target),))

    assert reason is None
    assert programs == ({
        "kind": "anchor_ray_extend",
        "background": 0,
        "mode": "down",
    },)


def test_program_derivation_rejects_shape_change() -> None:
    programs, reason = ray_extend_programs((
        ([[1, 0], [0, 0]], [[1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_SHAPE_PRESERVING_RAY_EXTENSION"


def test_program_derivation_skips_noop_demonstration() -> None:
    programs, reason = ray_extend_programs((
        ([[1, 1], [1, 1]], [[1, 1], [1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_RAY_EXTENSION"


def test_two_training_gaps_become_exact_trace_explained_acceptances() -> None:
    for task_id in _TASK_IDS:
        result = grid_induction.run_public_task_v2_2(
            public_task(task_id),
            engine=None,
            mechanistic=True,
        )

        assert result["predictions"] == expected_predictions(task_id)
        trace = result["mechanistic_trace"]
        final = [item for item in trace["events"] if item["event"] == "final_decision"][0]
        successes = [
            item
            for item in trace["events"]
            if item.get("event") == "hidden_execution"
            and item.get("candidate_kind") == "anchor_ray_extend"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("ray_extend:")
        assert successes
