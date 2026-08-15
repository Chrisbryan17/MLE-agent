from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.line_connect import (
    apply_line_connect,
    line_connect_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "line_connect"
_TASK_IDS = ("1f876c06", "22168020", "22eb0ac0", "ded97339")


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


def test_horizontal_connection_fills_between_same_color_anchors() -> None:
    assert apply_line_connect(
        {"kind": "same_color_line_connect", "background": 0, "mode": "horizontal"},
        [[1, 0, 0, 1], [0, 0, 0, 0]],
    ) == [[1, 1, 1, 1], [0, 0, 0, 0]]


def test_vertical_connection_fills_between_same_color_anchors() -> None:
    assert apply_line_connect(
        {"kind": "same_color_line_connect", "background": 0, "mode": "vertical"},
        [[2, 0], [0, 0], [2, 0]],
    ) == [[2, 0], [2, 0], [2, 0]]


def test_diagonal_connection_fills_both_diagonal_families() -> None:
    source = [
        [3, 0, 0, 0],
        [0, 0, 0, 4],
        [0, 0, 3, 0],
        [0, 4, 0, 0],
    ]

    assert apply_line_connect(
        {"kind": "same_color_line_connect", "background": 0, "mode": "diagonal"},
        source,
    ) == [
        [3, 0, 0, 0],
        [0, 3, 0, 4],
        [0, 4, 3, 0],
        [0, 4, 0, 0],
    ]


def test_newly_filled_cells_do_not_become_anchors() -> None:
    source = [
        [5, 0, 5],
        [0, 0, 0],
        [0, 5, 0],
    ]

    assert apply_line_connect(
        {"kind": "same_color_line_connect", "background": 0, "mode": "orthogonal"},
        source,
    ) == [
        [5, 5, 5],
        [0, 0, 0],
        [0, 5, 0],
    ]


def test_connection_rejects_cross_color_overwrite() -> None:
    with pytest.raises(ValueError, match="line connection color conflict"):
        apply_line_connect(
            {"kind": "same_color_line_connect", "background": 0, "mode": "horizontal"},
            [[1, 2, 1]],
        )


def test_program_derivation_returns_unique_horizontal_candidate() -> None:
    source = [
        [1, 0, 0, 1],
        [2, 0, 0, 0],
        [0, 0, 0, 0],
        [2, 0, 0, 0],
    ]
    target = [
        [1, 1, 1, 1],
        [2, 0, 0, 0],
        [0, 0, 0, 0],
        [2, 0, 0, 0],
    ]

    programs, reason = line_connect_programs(((source, target),))

    assert reason is None
    assert programs == ({
        "kind": "same_color_line_connect",
        "background": 0,
        "mode": "horizontal",
    },)


def test_program_derivation_rejects_shape_change() -> None:
    programs, reason = line_connect_programs((
        ([[1, 0, 1]], [[1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_SHAPE_PRESERVING_LINE_CONNECT"


def test_program_derivation_skips_noop_demonstration() -> None:
    programs, reason = line_connect_programs((
        ([[1, 1, 1]], [[1, 1, 1]]),
    ))

    assert programs == ()
    assert reason == "NO_LINE_CONNECTION"


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
            and item.get("candidate_kind") == "same_color_line_connect"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("line_connect:")
        assert successes
