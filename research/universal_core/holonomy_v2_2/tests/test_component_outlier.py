from __future__ import annotations

from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.component_outlier import (
    apply_component_outlier,
    component_outlier_programs,
)


def test_outlier_programs_infer_unique_minimum_and_uniform_peers() -> None:
    demos = (
        (
            [[8, 8, 0, 8, 8, 8, 0, 8, 8, 8]],
            [[2, 2, 0, 1, 1, 1, 0, 1, 1, 1]],
        ),
        (
            [[8, 0, 8, 8, 0, 8, 8]],
            [[2, 0, 1, 1, 0, 1, 1]],
        ),
    )

    programs, reason = component_outlier_programs(demos)

    assert reason is None
    assert programs == (
        {
            "kind": "component_area_outlier_color",
            "background": 0,
            "connectivity": 4,
            "selector": "minimum",
            "selected_color": 2,
            "other_color": 1,
        },
        {
            "kind": "component_area_outlier_color",
            "background": 0,
            "connectivity": 8,
            "selector": "minimum",
            "selected_color": 2,
            "other_color": 1,
        },
    )


def test_hidden_topology_rejects_four_connectivity_and_accepts_eight() -> None:
    hidden = [
        [0, 8, 8, 0, 0, 0, 8, 8, 8, 0],
        [0, 0, 8, 0, 0, 0, 0, 0, 8, 0],
        [0, 8, 0, 0, 0, 0, 0, 8, 0, 0],
        [0, 8, 8, 8, 0, 0, 8, 8, 8, 8],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 8, 8, 8, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 8, 0, 0, 0, 0],
        [0, 0, 0, 0, 8, 0, 0, 0, 0, 0],
        [0, 0, 0, 8, 8, 8, 8, 0, 0, 0],
    ]
    base = {
        "kind": "component_area_outlier_color",
        "background": 0,
        "selector": "minimum",
        "selected_color": 2,
        "other_color": 1,
    }

    with pytest.raises(ValueError, match="component peer areas must be uniform"):
        apply_component_outlier({**base, "connectivity": 4}, hidden)

    assert apply_component_outlier({**base, "connectivity": 8}, hidden) == [
        [0, 2, 2, 0, 0, 0, 1, 1, 1, 0],
        [0, 0, 2, 0, 0, 0, 0, 0, 1, 0],
        [0, 2, 0, 0, 0, 0, 0, 1, 0, 0],
        [0, 2, 2, 2, 0, 0, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
    ]


def test_outlier_programs_report_missing_common_background() -> None:
    programs, reason = component_outlier_programs((
        ([[0, 8, 8]], [[0, 2, 2]]),
        ([[3, 8, 8]], [[3, 2, 2]]),
    ))

    assert programs == ()
    assert reason == "NO_BACKGROUND_CANDIDATE"


def b230c067_task() -> dict[str, Any]:
    return {
        "task_id": "b230c067",
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": [
            {
                "input": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 8, 8, 8, 8],
                    [0, 8, 8, 8, 8, 0, 0, 0, 8, 8],
                    [0, 0, 0, 8, 8, 0, 0, 0, 8, 8],
                    [0, 0, 0, 8, 8, 8, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 8, 8, 8, 8, 0, 0, 0],
                    [0, 0, 0, 0, 0, 8, 8, 0, 0, 0],
                    [0, 0, 0, 0, 0, 8, 8, 8, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ],
                "output": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 2, 2, 2, 2],
                    [0, 1, 1, 1, 1, 0, 0, 0, 2, 2],
                    [0, 0, 0, 1, 1, 0, 0, 0, 2, 2],
                    [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
                    [0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                    [0, 0, 0, 0, 0, 1, 1, 1, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ],
            },
            {
                "input": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 8, 8, 8],
                    [0, 8, 8, 8, 8, 0, 0, 8, 0, 8],
                    [0, 8, 0, 0, 8, 0, 0, 8, 8, 8],
                    [0, 8, 8, 8, 8, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 8, 8, 8, 8, 0],
                    [0, 0, 0, 0, 0, 8, 0, 0, 8, 0],
                    [0, 0, 0, 0, 0, 8, 8, 8, 8, 0],
                ],
                "output": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 2, 2, 2],
                    [0, 1, 1, 1, 1, 0, 0, 2, 0, 2],
                    [0, 1, 0, 0, 1, 0, 0, 2, 2, 2],
                    [0, 1, 1, 1, 1, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 1, 1, 1, 1, 0],
                    [0, 0, 0, 0, 0, 1, 0, 0, 1, 0],
                    [0, 0, 0, 0, 0, 1, 1, 1, 1, 0],
                ],
            },
            {
                "input": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 8, 8, 8, 0, 0, 0, 0, 0, 0],
                    [0, 8, 0, 8, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [8, 8, 0, 0, 0, 0, 0, 0, 0, 0],
                    [8, 8, 0, 8, 8, 8, 0, 0, 0, 0],
                    [0, 0, 0, 8, 0, 8, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ],
                "output": [
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 1, 1, 1, 0, 0, 0, 0, 0, 0],
                    [0, 1, 0, 1, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [2, 2, 0, 0, 0, 0, 0, 0, 0, 0],
                    [2, 2, 0, 1, 1, 1, 0, 0, 0, 0],
                    [0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ],
            },
        ],
        "hidden_inputs": [[
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 8, 8, 0, 0, 0, 8, 8, 8, 0],
            [0, 0, 8, 0, 0, 0, 0, 0, 8, 0],
            [0, 8, 0, 0, 0, 0, 0, 8, 0, 0],
            [0, 8, 8, 8, 0, 0, 8, 8, 8, 8],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 8, 8, 8, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 8, 0, 0, 0, 0],
            [0, 0, 0, 0, 8, 0, 0, 0, 0, 0],
            [0, 0, 0, 8, 8, 8, 8, 0, 0, 0],
        ]],
    }


def test_exact_rank_failure_becomes_trace_explained_acceptance() -> None:
    result = grid_induction.run_public_task_v2_2(
        b230c067_task(),
        engine=None,
        mechanistic=True,
    )
    expected = [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 2, 2, 0, 0, 0, 1, 1, 1, 0],
        [0, 0, 2, 0, 0, 0, 0, 0, 1, 0],
        [0, 2, 0, 0, 0, 0, 0, 1, 0, 0],
        [0, 2, 2, 2, 0, 0, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
    ]

    assert result["predictions"] == [{"status": "ACCEPTED", "prediction": expected}]
    events = result["mechanistic_trace"]["events"]
    rank_failures = [
        event
        for event in events
        if event.get("event") == "hidden_execution"
        and event.get("candidate_kind") == "component_rank_color"
        and event.get("outcome") == "FAILED"
        and event.get("exception_type") == "KeyError"
        and "unmapped component rank" in event.get("exception_message", "")
    ]
    assert len(rank_failures) == 2
    outlier_failures = [
        event
        for event in events
        if event.get("event") == "hidden_execution"
        and event.get("candidate_kind") == "component_area_outlier_color"
        and event.get("outcome") == "FAILED"
        and event.get("exception_type") == "ValueError"
        and "component peer areas must be uniform" in event.get("exception_message", "")
    ]
    outlier_successes = [
        event
        for event in events
        if event.get("event") == "hidden_execution"
        and event.get("candidate_kind") == "component_area_outlier_color"
        and event.get("outcome") == "SUCCEEDED"
    ]
    assert len(outlier_failures) == 1
    assert len(outlier_successes) == 1
    final = [event for event in events if event.get("event") == "final_decision"]
    assert final[0]["status"] == "ACCEPTED"
    assert final[0]["selected_candidate_id"].startswith("component_outlier:")
