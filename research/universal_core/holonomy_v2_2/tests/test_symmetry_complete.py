from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.symmetry_complete import (
    apply_symmetry_complete,
    symmetry_complete_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "symmetry_complete"
_EXACT_TASK_IDS = ("496994bd", "e729b7be", "f25ffba3")


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


def test_vertical_completion_reflects_columns() -> None:
    assert apply_symmetry_complete(
        {"kind": "reflective_symmetry_complete", "background": 0, "transform": "vertical"},
        [[1, 0, 0], [0, 2, 0]],
    ) == [[1, 0, 1], [0, 2, 0]]


def test_horizontal_completion_reflects_rows() -> None:
    assert apply_symmetry_complete(
        {"kind": "reflective_symmetry_complete", "background": 0, "transform": "horizontal"},
        [[1, 0, 0], [0, 2, 0]],
    ) == [[1, 2, 0], [1, 2, 0]]


def test_rotate_180_completion_preserves_original_cells() -> None:
    assert apply_symmetry_complete(
        {"kind": "reflective_symmetry_complete", "background": 0, "transform": "rotate_180"},
        [[1, 0, 0], [0, 0, 0]],
    ) == [[1, 0, 0], [0, 0, 1]]


def test_diagonal_completion_uses_original_anchors_only() -> None:
    source = [[3, 0, 0], [0, 0, 4], [0, 0, 0]]
    assert apply_symmetry_complete(
        {"kind": "reflective_symmetry_complete", "background": 0, "transform": "main_diagonal"},
        source,
    ) == [[3, 0, 0], [0, 0, 4], [0, 4, 0]]


def test_symmetry_completion_rejects_cross_color_overwrite() -> None:
    with pytest.raises(ValueError, match="symmetry completion color conflict"):
        apply_symmetry_complete(
            {"kind": "reflective_symmetry_complete", "background": 0, "transform": "vertical"},
            [[1, 2]],
        )


def test_diagonal_completion_rejects_non_square_grid() -> None:
    with pytest.raises(ValueError, match="diagonal symmetry requires a square grid"):
        apply_symmetry_complete(
            {"kind": "reflective_symmetry_complete", "background": 0, "transform": "anti_diagonal"},
            [[1, 0, 0], [0, 0, 0]],
        )


def test_program_derivation_returns_unique_horizontal_candidate() -> None:
    source = [[1, 0, 0], [0, 2, 0]]
    target = [[1, 2, 0], [1, 2, 0]]

    programs, reason = symmetry_complete_programs(((source, target),))

    assert reason is None
    assert programs == ({
        "kind": "reflective_symmetry_complete",
        "background": 0,
        "transform": "horizontal",
    },)


def test_program_derivation_rejects_shape_change() -> None:
    programs, reason = symmetry_complete_programs((
        ([[1, 0], [0, 0]], [[1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_SHAPE_PRESERVING_SYMMETRY"


def test_program_derivation_skips_noop_demonstration() -> None:
    programs, reason = symmetry_complete_programs((
        ([[1, 1], [1, 1]], [[1, 1], [1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_REFLECTIVE_SYMMETRY_COMPLETION"


def test_three_training_gaps_become_exact_trace_explained_acceptances() -> None:
    for task_id in _EXACT_TASK_IDS:
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
            and item.get("candidate_kind") == "reflective_symmetry_complete"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("symmetry_complete:")
        assert successes


def test_b8825c91_preserves_hidden_symmetry_ambiguity() -> None:
    result = grid_induction.run_public_task_v2_2(
        public_task("b8825c91"),
        engine=None,
        mechanistic=True,
    )

    assert result["predictions"] == [
        {"status": "AMBIGUOUS_PROGRAM", "prediction": None}
    ]
    trace = result["mechanistic_trace"]
    classes = [
        item
        for item in trace["events"]
        if item["event"] == "equivalence_class"
        and any(
            str(candidate_id).startswith("symmetry_complete:")
            for candidate_id in item["candidate_ids"]
        )
    ]
    assert trace["terminal_status"] == "AMBIGUOUS_PROGRAM"
    assert len(classes) >= 2
