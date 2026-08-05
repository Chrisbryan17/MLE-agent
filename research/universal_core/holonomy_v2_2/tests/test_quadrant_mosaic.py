from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.quadrant_mosaic import (
    apply_quadrant_mosaic,
    quadrant_mosaic_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "quadrant_mosaic"
_TASK_IDS = (
    "0c786b71",
    "3af2c5a8",
    "46442a0e",
    "62c24649",
    "67e8384a",
    "7953d61e",
    "7fe24cdd",
    "833dafe3",
    "ed98d772",
)


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
    payload = load_payload(task_id)
    return [
        {"status": "ACCEPTED", "prediction": item["output"]}
        for item in payload["test"]
    ]


def test_apply_standard_reflected_quadrant_mosaic() -> None:
    program = {
        "kind": "dihedral_quadrant_mosaic",
        "top_left": "identity",
        "top_right": "reflect_columns",
        "bottom_left": "reflect_rows",
        "bottom_right": "rotate_180",
    }

    assert apply_quadrant_mosaic(program, [[1, 2], [3, 4]]) == [
        [1, 2, 2, 1],
        [3, 4, 4, 3],
        [3, 4, 4, 3],
        [1, 2, 2, 1],
    ]


def test_apply_rejects_output_beyond_arc_bounds() -> None:
    source = [[0] * 16 for _ in range(16)]
    program = {
        "kind": "dihedral_quadrant_mosaic",
        "top_left": "identity",
        "top_right": "identity",
        "bottom_left": "identity",
        "bottom_right": "identity",
    }

    with pytest.raises(ValueError, match="exceeds ARC bounds"):
        apply_quadrant_mosaic(program, source)


def test_program_derivation_returns_one_canonical_program() -> None:
    source = [[1, 2], [3, 4]]
    target = [
        [1, 2, 2, 1],
        [3, 4, 4, 3],
        [3, 4, 4, 3],
        [1, 2, 2, 1],
    ]

    programs, reason = quadrant_mosaic_programs(((source, target),))

    assert reason is None
    assert programs == ({
        "kind": "dihedral_quadrant_mosaic",
        "top_left": "identity",
        "top_right": "reflect_columns",
        "bottom_left": "reflect_rows",
        "bottom_right": "rotate_180",
    },)


def test_program_derivation_reports_non_double_output_shape() -> None:
    programs, reason = quadrant_mosaic_programs((
        ([[1, 2], [3, 4]], [[1, 2], [3, 4]]),
    ))

    assert programs == ()
    assert reason == "OUTPUT_NOT_DOUBLE_SOURCE_SHAPE"


def test_nine_training_gaps_become_exact_trace_explained_acceptances() -> None:
    for task_id in _TASK_IDS:
        result = grid_induction.run_public_task_v2_2(
            public_task(task_id),
            engine=None,
            mechanistic=True,
        )

        assert result["predictions"] == expected_predictions(task_id)
        trace = result["mechanistic_trace"]
        final = [
            item for item in trace["events"]
            if item["event"] == "final_decision"
        ]
        successes = [
            item
            for item in trace["events"]
            if item.get("event") == "hidden_execution"
            and item.get("candidate_kind") == "dihedral_quadrant_mosaic"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final[0]["status"] == "ACCEPTED"
        assert final[0]["selected_candidate_id"].startswith("quadrant_mosaic:")
        assert successes


def test_symmetric_demonstration_preserves_hidden_transform_ambiguity() -> None:
    task = {
        "task_id": "quadrant-mosaic-ambiguity",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": [{
            "input": [[1, 1], [1, 1]],
            "output": [
                [1, 1, 1, 1],
                [1, 1, 1, 1],
                [1, 1, 1, 1],
                [1, 1, 1, 1],
            ],
        }],
        "hidden_inputs": [[[1, 2], [3, 4]]],
    }

    result = grid_induction.run_public_task_v2_2(
        task,
        engine=None,
        mechanistic=True,
    )

    assert result["predictions"] == [
        {"status": "AMBIGUOUS_PROGRAM", "prediction": None}
    ]
    classes = [
        item
        for item in result["mechanistic_trace"]["events"]
        if item["event"] == "equivalence_class"
        and any(
            str(candidate_id).startswith("quadrant_mosaic:")
            for candidate_id in item["candidate_ids"]
        )
    ]
    assert len(classes) >= 2
