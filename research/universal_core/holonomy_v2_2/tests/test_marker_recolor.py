from __future__ import annotations

from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.marker_recolor import (
    apply_marker_recolor,
    marker_recolor_programs,
)


def test_marker_programs_infer_dynamic_marker_recoloring() -> None:
    demos = (
        (
            [[0, 3, 3], [0, 3, 0], [6, 0, 0]],
            [[0, 6, 6], [0, 6, 0], [0, 0, 0]],
        ),
        (
            [[0, 2, 2], [0, 0, 2], [4, 0, 0]],
            [[0, 4, 4], [0, 0, 4], [0, 0, 0]],
        ),
    )

    programs, reason = marker_recolor_programs(demos)

    assert reason is None
    assert programs == (
        {"kind": "marker_recolor", "background": 0, "connectivity": 4},
        {"kind": "marker_recolor", "background": 0, "connectivity": 8},
    )
    hidden = [[0, 8, 8], [0, 8, 0], [2, 0, 0]]
    expected = [[0, 2, 2], [0, 2, 0], [0, 0, 0]]
    assert {tuple(map(tuple, apply_marker_recolor(program, hidden))) for program in programs} == {
        tuple(map(tuple, expected))
    }


def test_marker_apply_rejects_multiple_singleton_components() -> None:
    program = {"kind": "marker_recolor", "background": 0, "connectivity": 4}

    with pytest.raises(ValueError, match="exactly one singleton marker"):
        apply_marker_recolor(program, [[6, 0, 7], [0, 3, 3]])


def test_marker_programs_report_missing_common_background() -> None:
    programs, reason = marker_recolor_programs((
        ([[0, 1]], [[0, 1]]),
        ([[2, 3]], [[2, 3]]),
    ))

    assert programs == ()
    assert reason == "NO_BACKGROUND_CANDIDATE"


def aabf363d_task() -> dict[str, Any]:
    return {
        "task_id": "aabf363d",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": [
            {
                "input": [
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 3, 0, 0, 0],
                    [0, 0, 3, 3, 3, 0, 0],
                    [0, 3, 3, 3, 3, 0, 0],
                    [0, 3, 3, 0, 0, 0, 0],
                    [0, 0, 3, 3, 0, 0, 0],
                    [6, 0, 0, 0, 0, 0, 0],
                ],
                "output": [
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 6, 0, 0, 0],
                    [0, 0, 6, 6, 6, 0, 0],
                    [0, 6, 6, 6, 6, 0, 0],
                    [0, 6, 6, 0, 0, 0, 0],
                    [0, 0, 6, 6, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0],
                ],
            },
            {
                "input": [
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 2, 2, 2, 0, 0, 0],
                    [0, 0, 2, 0, 0, 0, 0],
                    [0, 2, 2, 2, 2, 0, 0],
                    [0, 0, 2, 2, 2, 0, 0],
                    [0, 0, 0, 2, 0, 0, 0],
                    [4, 0, 0, 0, 0, 0, 0],
                ],
                "output": [
                    [0, 0, 0, 0, 0, 0, 0],
                    [0, 4, 4, 4, 0, 0, 0],
                    [0, 0, 4, 0, 0, 0, 0],
                    [0, 4, 4, 4, 4, 0, 0],
                    [0, 0, 4, 4, 4, 0, 0],
                    [0, 0, 0, 4, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0],
                ],
            },
        ],
        "hidden_inputs": [[
            [0, 0, 0, 0, 0, 0, 0],
            [0, 8, 8, 8, 0, 0, 0],
            [0, 8, 8, 8, 8, 8, 0],
            [0, 0, 0, 8, 8, 0, 0],
            [0, 0, 8, 8, 0, 0, 0],
            [0, 0, 8, 8, 8, 0, 0],
            [2, 0, 0, 0, 0, 0, 0],
        ]],
    }


def test_exact_execution_failure_becomes_trace_explained_acceptance() -> None:
    result = grid_induction.run_public_task_v2_2(
        aabf363d_task(),
        engine=None,
        mechanistic=True,
    )
    expected = [
        [0, 0, 0, 0, 0, 0, 0],
        [0, 2, 2, 2, 0, 0, 0],
        [0, 2, 2, 2, 2, 2, 0],
        [0, 0, 0, 2, 2, 0, 0],
        [0, 0, 2, 2, 0, 0, 0],
        [0, 0, 2, 2, 2, 0, 0],
        [0, 0, 0, 0, 0, 0, 0],
    ]

    assert result["predictions"] == [{"status": "ACCEPTED", "prediction": expected}]
    events = result["mechanistic_trace"]["events"]
    assert any(
        event.get("event") == "hidden_execution"
        and event.get("candidate_kind") == "color_map"
        and event.get("outcome") == "FAILED"
        and event.get("exception_type") == "KeyError"
        and "unmapped grid cell" in event.get("exception_message", "")
        for event in events
    )
    marker_successes = [
        event
        for event in events
        if event.get("event") == "hidden_execution"
        and event.get("candidate_kind") == "marker_recolor"
        and event.get("outcome") == "SUCCEEDED"
    ]
    assert len(marker_successes) == 2
    final = [event for event in events if event.get("event") == "final_decision"]
    assert final[0]["status"] == "ACCEPTED"
    assert final[0]["selected_candidate_id"].startswith("marker_recolor:")
