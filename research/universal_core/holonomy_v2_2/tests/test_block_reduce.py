from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.block_reduce import (
    apply_block_reduce,
    block_reduce_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "block_reduce"
_TASK_IDS = ("5614dbcf", "68b67ca3")


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


def test_strict_mode_reduces_each_fixed_block() -> None:
    program = {
        "kind": "fixed_block_reduce",
        "row_factor": 2,
        "col_factor": 2,
        "reducer": "strict_mode",
    }
    source = [
        [1, 1, 2, 2],
        [1, 0, 2, 2],
        [3, 3, 4, 4],
        [3, 3, 4, 0],
    ]

    assert apply_block_reduce(program, source) == [[1, 2], [3, 4]]


def test_strict_mode_rejects_tied_block() -> None:
    program = {
        "kind": "fixed_block_reduce",
        "row_factor": 2,
        "col_factor": 2,
        "reducer": "strict_mode",
    }

    with pytest.raises(ValueError, match="unique mode"):
        apply_block_reduce(program, [[1, 2], [2, 1]])


def test_unique_non_background_reduces_sparse_blocks() -> None:
    program = {
        "kind": "fixed_block_reduce",
        "row_factor": 2,
        "col_factor": 2,
        "reducer": "unique_non_background",
        "background": 0,
    }
    source = [
        [3, 0, 0, 4],
        [0, 0, 0, 0],
        [0, 5, 0, 0],
        [0, 0, 0, 0],
    ]

    assert apply_block_reduce(program, source) == [[3, 4], [5, 0]]


def test_unique_non_background_rejects_conflicting_block() -> None:
    program = {
        "kind": "fixed_block_reduce",
        "row_factor": 2,
        "col_factor": 2,
        "reducer": "unique_non_background",
        "background": 0,
    }

    with pytest.raises(ValueError, match="one non-background color"):
        apply_block_reduce(program, [[1, 2], [0, 0]])


def test_program_derivation_exposes_stable_block_factors() -> None:
    demos = (
        (
            [[1, 1, 2, 2], [1, 0, 2, 2], [3, 3, 4, 4], [3, 3, 4, 0]],
            [[1, 2], [3, 4]],
        ),
        (
            [[5, 5, 6, 6], [5, 0, 6, 6], [7, 7, 8, 8], [7, 7, 8, 0]],
            [[5, 6], [7, 8]],
        ),
    )

    programs, reason = block_reduce_programs(demos)

    assert reason is None
    assert {
        (item["row_factor"], item["col_factor"], item["reducer"])
        for item in programs
    } >= {(2, 2, "strict_mode")}


def test_program_derivation_rejects_unstable_block_factors() -> None:
    demos = (
        ([[1, 1], [1, 1]], [[1]]),
        ([[2, 2, 2]], [[2]]),
    )

    programs, reason = block_reduce_programs(demos)

    assert programs == ()
    assert reason == "NO_STABLE_BLOCK_FACTORS"


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
            and item.get("candidate_kind") == "fixed_block_reduce"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final["selected_candidate_id"].startswith("block_reduce:")
        assert successes
