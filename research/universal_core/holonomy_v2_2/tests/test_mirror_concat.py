from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.mirror_concat import (
    apply_mirror_concat,
    mirror_concat_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "mirror_concat"
_TASK_IDS = ("4c4377d9", "6d0aefbc", "6fa7a44f", "8be77c9e", "c9e6f938")


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


def test_row_source_first_appends_vertical_reflection() -> None:
    program = {
        "kind": "mirror_concatenate",
        "axis": "rows",
        "order": "source_first",
    }

    assert apply_mirror_concat(program, [[1, 2], [3, 4]]) == [
        [1, 2],
        [3, 4],
        [3, 4],
        [1, 2],
    ]


def test_row_reflection_first_prepends_vertical_reflection() -> None:
    program = {
        "kind": "mirror_concatenate",
        "axis": "rows",
        "order": "reflection_first",
    }

    assert apply_mirror_concat(program, [[1, 2], [3, 4]]) == [
        [3, 4],
        [1, 2],
        [1, 2],
        [3, 4],
    ]


def test_column_orders_append_or_prepend_horizontal_reflection() -> None:
    source = [[1, 2], [3, 4]]

    assert apply_mirror_concat({
        "kind": "mirror_concatenate",
        "axis": "columns",
        "order": "source_first",
    }, source) == [
        [1, 2, 2, 1],
        [3, 4, 4, 3],
    ]
    assert apply_mirror_concat({
        "kind": "mirror_concatenate",
        "axis": "columns",
        "order": "reflection_first",
    }, source) == [
        [2, 1, 1, 2],
        [4, 3, 3, 4],
    ]


def test_program_enumeration_exposes_all_four_structural_hypotheses() -> None:
    programs, reason = mirror_concat_programs((([[1]], [[1], [1]]),))

    assert reason is None
    assert programs == (
        {"kind": "mirror_concatenate", "axis": "rows", "order": "source_first"},
        {"kind": "mirror_concatenate", "axis": "rows", "order": "reflection_first"},
        {"kind": "mirror_concatenate", "axis": "columns", "order": "source_first"},
        {"kind": "mirror_concatenate", "axis": "columns", "order": "reflection_first"},
    )


def test_five_training_gaps_become_exact_trace_explained_acceptances() -> None:
    for task_id in _TASK_IDS:
        result = grid_induction.run_public_task_v2_2(
            public_task(task_id),
            engine=None,
            mechanistic=True,
        )

        assert result["predictions"] == expected_predictions(task_id)
        trace = result["mechanistic_trace"]
        final = [item for item in trace["events"] if item["event"] == "final_decision"]
        successes = [
            item
            for item in trace["events"]
            if item.get("event") == "hidden_execution"
            and item.get("candidate_kind") == "mirror_concatenate"
            and item.get("outcome") == "SUCCEEDED"
        ]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final[0]["status"] == "ACCEPTED"
        assert final[0]["selected_candidate_id"].startswith("mirror_concat:")
        assert successes
