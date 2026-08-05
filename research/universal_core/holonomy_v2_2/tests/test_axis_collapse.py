from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.axis_collapse import (
    apply_axis_collapse,
    axis_collapse_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "axis_collapse"
_TASK_IDS = (
    "2dee498d",
    "746b3537",
    "7b7f7511",
    "ce8d95cc",
    "e1baa8a4",
    "eb5a1d5d",
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
    return [
        {"status": "ACCEPTED", "prediction": item["output"]}
        for item in load_payload(task_id)["test"]
    ]


def test_adjacent_run_collapse_rows_columns_and_both() -> None:
    source = [
        [1, 1, 2],
        [1, 1, 2],
        [3, 3, 4],
    ]

    assert apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "rows",
    }, source) == [
        [1, 1, 2],
        [3, 3, 4],
    ]
    assert apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "columns",
    }, source) == [
        [1, 2],
        [1, 2],
        [3, 4],
    ]
    assert apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "both",
    }, source) == [
        [1, 2],
        [3, 4],
    ]


def test_global_first_collapse_preserves_first_occurrence_order() -> None:
    source = [
        [1, 2, 1],
        [3, 4, 3],
        [1, 2, 1],
    ]

    assert apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "global_first",
        "axes": "both",
    }, source) == [
        [1, 2],
        [3, 4],
    ]


def test_row_and_column_collapse_commute() -> None:
    source = [
        [1, 1, 2, 2],
        [1, 1, 2, 2],
        [3, 3, 4, 4],
    ]
    rows_then_columns = apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "both",
    }, source)
    columns_only = apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "columns",
    }, source)
    columns_then_rows = apply_axis_collapse({
        "kind": "axis_duplicate_collapse",
        "scope": "adjacent_runs",
        "axes": "rows",
    }, columns_only)

    assert rows_then_columns == columns_then_rows == [[1, 2], [3, 4]]


def test_program_derivation_skips_when_no_axis_reduction_occurs() -> None:
    programs, reason = axis_collapse_programs((
        ([[1, 2], [3, 4]], [[1, 2], [3, 4]]),
    ))

    assert programs == ()
    assert reason == "NO_DUPLICATE_AXIS_REDUCTION"


def test_six_training_gaps_become_exact_trace_explained_acceptances() -> None:
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
            and item.get("candidate_kind") == "axis_duplicate_collapse"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("axis_collapse:")
        assert successes
