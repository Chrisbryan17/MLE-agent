from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.bbox_complete import (
    apply_bbox_complete,
    bbox_complete_programs,
)


_FIXTURES = Path(__file__).parent / "fixtures" / "bbox"


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


def test_global_fill_preserves_existing_cells() -> None:
    program = {
        "kind": "bounding_box_complete",
        "background": 0,
        "fill_color": 2,
        "mode": "fill",
        "scope": "global",
    }

    assert apply_bbox_complete(program, [
        [0, 8, 0],
        [0, 0, 0],
        [0, 0, 8],
    ]) == [
        [0, 8, 2],
        [0, 2, 2],
        [0, 2, 8],
    ]


def test_global_outline_only_completes_border() -> None:
    program = {
        "kind": "bounding_box_complete",
        "background": 0,
        "fill_color": 1,
        "mode": "outline",
        "scope": "global",
    }

    assert apply_bbox_complete(program, [
        [8, 0, 0, 8],
        [0, 0, 0, 0],
        [8, 0, 0, 8],
    ]) == [
        [8, 1, 1, 8],
        [1, 0, 0, 1],
        [8, 1, 1, 8],
    ]


def test_component_fill_completes_each_object_independently() -> None:
    program = {
        "kind": "bounding_box_complete",
        "background": 0,
        "fill_color": 1,
        "mode": "fill",
        "scope": "components",
        "connectivity": 4,
    }

    assert apply_bbox_complete(program, [
        [8, 8, 0, 0, 8],
        [8, 0, 0, 0, 8],
        [0, 0, 0, 0, 8],
    ]) == [
        [8, 8, 0, 0, 8],
        [8, 1, 0, 0, 8],
        [0, 0, 0, 0, 8],
    ]


def test_program_enumeration_exposes_fill_outline_global_and_component_modes() -> None:
    demos = ((
        [[8, 0], [0, 8]],
        [[8, 1], [1, 8]],
    ),)

    programs, reason = bbox_complete_programs(demos)

    assert reason is None
    assert any(item["scope"] == "global" and item["mode"] == "fill" for item in programs)
    assert any(item["scope"] == "global" and item["mode"] == "outline" for item in programs)
    assert any(item["scope"] == "components" and item["connectivity"] == 4 for item in programs)
    assert any(item["scope"] == "components" and item["connectivity"] == 8 for item in programs)


def test_three_training_defects_become_exact_trace_explained_acceptances() -> None:
    for task_id in ("3aa6fb7a", "6d75e8bb", "e7639916"):
        result = grid_induction.run_public_task_v2_2(
            public_task(task_id),
            engine=None,
            mechanistic=True,
        )

        assert result["predictions"] == expected_predictions(task_id)
        trace = result["mechanistic_trace"]
        final = [item for item in trace["events"] if item["event"] == "final_decision"]
        assert trace["terminal_status"] == "ACCEPTED"
        assert final[0]["status"] == "ACCEPTED"
        assert final[0]["selected_candidate_id"].startswith("bbox_complete:")
        assert any(
            item.get("event") == "hidden_execution"
            and item.get("candidate_kind") == "bounding_box_complete"
            and item.get("outcome") == "SUCCEEDED"
            for item in trace["events"]
        )


def test_connectivity_disagreement_remains_ambiguous() -> None:
    result = grid_induction.run_public_task_v2_2(
        public_task("60b61512"),
        engine=None,
        mechanistic=True,
    )
    trace = result["mechanistic_trace"]
    classes = [item for item in trace["events"] if item["event"] == "equivalence_class"]
    bbox_members = [
        candidate_id
        for item in classes
        for candidate_id in item["candidate_ids"]
        if candidate_id.startswith("bbox_complete:")
    ]

    assert result["predictions"] == [
        {"status": "AMBIGUOUS_PROGRAM", "prediction": None}
    ]
    assert trace["terminal_status"] == "AMBIGUOUS_PROGRAM"
    assert len(classes) > 1
    assert bbox_members
