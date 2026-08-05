from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.palette_repeat import (
    apply_palette_repeat,
    palette_repeat_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "palette_repeat"
_TASK_IDS = ("a59b95c0", "ac0a08a4", "b91ae062", "d4b1c2b1")


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


def test_apply_scales_by_total_palette_size() -> None:
    program = {
        "kind": "palette_cardinality_repeat",
        "operation": "scale",
        "statistic": "distinct_all",
    }

    assert apply_palette_repeat(program, [[1, 2], [2, 1]]) == [
        [1, 1, 2, 2],
        [1, 1, 2, 2],
        [2, 2, 1, 1],
        [2, 2, 1, 1],
    ]


def test_apply_tiles_by_total_palette_size() -> None:
    program = {
        "kind": "palette_cardinality_repeat",
        "operation": "tile",
        "statistic": "distinct_all",
    }

    assert apply_palette_repeat(program, [[1, 2]]) == [
        [1, 2, 1, 2],
        [1, 2, 1, 2],
    ]


def test_apply_scales_by_non_background_palette_size() -> None:
    program = {
        "kind": "palette_cardinality_repeat",
        "operation": "scale",
        "statistic": "distinct_non_background",
        "background": 0,
    }

    assert apply_palette_repeat(program, [[0, 1, 2]]) == [
        [0, 0, 1, 1, 2, 2],
        [0, 0, 1, 1, 2, 2],
    ]


def test_program_derivation_requires_demonstrated_factor_variation() -> None:
    demos = (
        (
            [[1, 2]],
            [[1, 1, 2, 2], [1, 1, 2, 2]],
        ),
        (
            [[3, 4, 5]],
            [
                [3, 3, 3, 4, 4, 4, 5, 5, 5],
                [3, 3, 3, 4, 4, 4, 5, 5, 5],
                [3, 3, 3, 4, 4, 4, 5, 5, 5],
            ],
        ),
    )

    programs, reason = palette_repeat_programs(demos)

    assert reason is None
    assert programs == ({
        "kind": "palette_cardinality_repeat",
        "operation": "scale",
        "statistic": "distinct_all",
    },)


def test_program_derivation_defers_constant_factor_to_fixed_grammar() -> None:
    demos = (
        (
            [[1, 2]],
            [[1, 1, 2, 2], [1, 1, 2, 2]],
        ),
        (
            [[3, 4]],
            [[3, 3, 4, 4], [3, 3, 4, 4]],
        ),
    )

    programs, reason = palette_repeat_programs(demos)

    assert programs == ()
    assert reason == "NO_FACTOR_VARIATION"


def test_apply_rejects_output_beyond_arc_bounds() -> None:
    program = {
        "kind": "palette_cardinality_repeat",
        "operation": "scale",
        "statistic": "distinct_all",
    }
    source = [[value for value in range(6)] for _ in range(6)]

    with pytest.raises(ValueError, match="exceeds ARC bounds"):
        apply_palette_repeat(program, source)


def test_four_training_gaps_become_exact_trace_explained_acceptances() -> None:
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
            and item.get("candidate_kind") == "palette_cardinality_repeat"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("palette_repeat:")
        assert successes
