from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.gravity_compact import (
    apply_gravity_compact,
    gravity_compact_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "gravity_compact"
_TASK_IDS = ("1e0a9b12", "3906de3d")


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


def test_vertical_gravity_compacts_up_and_down() -> None:
    source = [[1, 0], [0, 2], [3, 0]]

    assert apply_gravity_compact(
        {"kind": "axis_gravity_compact", "background": 0, "direction": "up"},
        source,
    ) == [[1, 2], [3, 0], [0, 0]]
    assert apply_gravity_compact(
        {"kind": "axis_gravity_compact", "background": 0, "direction": "down"},
        source,
    ) == [[0, 0], [1, 0], [3, 2]]


def test_horizontal_gravity_compacts_left_and_right() -> None:
    source = [[1, 0, 2, 0], [0, 3, 0, 4]]

    assert apply_gravity_compact(
        {"kind": "axis_gravity_compact", "background": 0, "direction": "left"},
        source,
    ) == [[1, 2, 0, 0], [3, 4, 0, 0]]
    assert apply_gravity_compact(
        {"kind": "axis_gravity_compact", "background": 0, "direction": "right"},
        source,
    ) == [[0, 0, 1, 2], [0, 0, 3, 4]]


def test_gravity_preserves_shape_counts_and_lane_order() -> None:
    source = [[4, 0, 7], [0, 8, 0], [4, 0, 9]]
    output = apply_gravity_compact(
        {"kind": "axis_gravity_compact", "background": 0, "direction": "down"},
        source,
    )

    assert (len(output), len(output[0])) == (len(source), len(source[0]))
    assert Counter(cell for row in output for cell in row) == Counter(
        cell for row in source for cell in row
    )
    for col in range(len(source[0])):
        before = [row[col] for row in source if row[col] != 0]
        after = [row[col] for row in output if row[col] != 0]
        assert after == before


def test_gravity_rejects_unknown_direction() -> None:
    with pytest.raises(ValueError, match="unknown gravity direction"):
        apply_gravity_compact(
            {"kind": "axis_gravity_compact", "background": 0, "direction": "diagonal"},
            [[1, 0], [0, 2]],
        )


def test_program_derivation_returns_unique_demonstrated_candidate() -> None:
    demos = ((
        [[1, 0], [0, 2], [3, 0]],
        [[0, 0], [1, 0], [3, 2]],
    ),)

    programs, reason = gravity_compact_programs(demos)

    assert reason is None
    assert programs == ({
        "kind": "axis_gravity_compact",
        "background": 0,
        "direction": "down",
    },)


def test_program_derivation_rejects_shape_change() -> None:
    programs, reason = gravity_compact_programs((
        ([[1, 0], [0, 2]], [[1, 2]]),
    ))

    assert programs == ()
    assert reason == "NO_SHAPE_PRESERVING_GRAVITY"


def test_program_derivation_skips_noop_demonstration() -> None:
    programs, reason = gravity_compact_programs((
        ([[1, 2], [0, 0]], [[1, 2], [0, 0]]),
    ))

    assert programs == ()
    assert reason == "NO_GRAVITY_COMPACTION"


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
            and item.get("candidate_kind") == "axis_gravity_compact"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("gravity_compact:")
        assert successes
