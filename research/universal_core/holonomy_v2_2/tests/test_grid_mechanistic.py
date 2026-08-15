from __future__ import annotations

import json
from typing import Any

from research.universal_core.holonomy_v2_2 import grid_induction
from research.universal_core.holonomy_v2_2.mechanistic_trace import validate_trace


def task(
    demos: list[dict[str, object]],
    hidden: list[object],
    task_id: str = "mechanistic-grid",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "instructions": "Infer the exact grid mapping.",
        "demonstrations": demos,
        "hidden_inputs": hidden,
    }


def without_trace(result: dict[str, Any]) -> dict[str, Any]:
    copied = dict(result)
    copied.pop("mechanistic_trace", None)
    return copied


def events(trace: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [item for item in trace["events"] if item["event"] == name]


def test_mechanistic_mode_has_exact_compact_parity() -> None:
    value = task(
        [{"input": [[0, 1]], "output": [[2, 3]]}],
        [[[1, 0]]],
        "parity",
    )

    compact = grid_induction.run_public_task_v2_2(value, engine=None)
    traced = grid_induction.run_public_task_v2_2(value, engine=None, mechanistic=True)

    assert "mechanistic_trace" not in compact
    assert without_trace(traced) == compact
    validate_trace(traced["mechanistic_trace"])


def test_trace_records_every_candidate_demonstration_and_terminal_fit() -> None:
    value = task(
        [{"input": [[1, 2]], "output": [[2, 1]]}],
        [[[3, 4]]],
        "candidate-ledger",
    )

    trace = grid_induction.run_public_task_v2_2(
        value,
        engine=None,
        mechanistic=True,
    )["mechanistic_trace"]
    proposed = events(trace, "candidate_proposed")
    executions = events(trace, "demo_execution")
    terminal = events(trace, "candidate_fit_decision")

    assert proposed
    assert len(proposed) == len(terminal)
    assert len(executions) == len(proposed)
    assert {item["decision"] for item in terminal} >= {
        "FITS_ALL_DEMOS",
        "DEMO_MISMATCH",
    }
    assert all("generator" in item and "program_ref" in item for item in proposed)
    validate_trace(trace)


def test_hidden_component_rank_key_error_is_fully_recorded() -> None:
    value = task(
        [{
            "input": [[5, 0, 5], [0, 0, 5]],
            "output": [[1, 0, 2], [0, 0, 2]],
        }],
        [[[5, 0, 5, 0, 5], [0, 0, 5, 0, 5], [0, 0, 0, 0, 5]]],
        "unseen-rank",
    )

    result = grid_induction.run_public_task_v2_2(value, None, mechanistic=True)
    rank_failures = [
        item
        for item in events(result["mechanistic_trace"], "hidden_execution")
        if item["outcome"] == "FAILED"
        and item["candidate_kind"] == "component_rank_color"
    ]

    assert result["predictions"] == [{"status": "EXECUTION_FAILED", "prediction": None}]
    assert rank_failures
    assert all(item["exception_type"] == "KeyError" for item in rank_failures)
    assert all("unmapped component rank" in item["exception_message"] for item in rank_failures)


def test_trace_replay_is_deterministic_and_task_id_independent() -> None:
    demos = [{"input": [[1, 2]], "output": [[2, 1]]}]
    first = grid_induction.run_public_task_v2_2(
        task(demos, [[[3, 4]]], "first"),
        None,
        mechanistic=True,
    )["mechanistic_trace"]
    replay = grid_induction.run_public_task_v2_2(
        task(demos, [[[3, 4]]], "first"),
        None,
        mechanistic=True,
    )["mechanistic_trace"]
    renamed = grid_induction.run_public_task_v2_2(
        task(demos, [[[3, 4]]], "second"),
        None,
        mechanistic=True,
    )["mechanistic_trace"]

    assert json.dumps(first, sort_keys=True) == json.dumps(replay, sort_keys=True)
    assert first["trace_digest"] == renamed["trace_digest"]
    assert first["envelope_digest"] != renamed["envelope_digest"]


def test_ambiguous_program_trace_lists_every_output_class() -> None:
    value = task(
        [{"input": [[1, 1], [1, 1]], "output": [[1, 1], [1, 1]]}],
        [[[1, 2], [3, 4]]],
        "ambiguous",
    )

    result = grid_induction.run_public_task_v2_2(value, None, mechanistic=True)
    trace = result["mechanistic_trace"]
    classes = events(trace, "equivalence_class")
    final = events(trace, "final_decision")

    assert result["predictions"] == [{"status": "AMBIGUOUS_PROGRAM", "prediction": None}]
    assert len(classes) > 1
    assert final == [
        {
            **final[0],
            "status": "AMBIGUOUS_PROGRAM",
        }
    ]
    assert set(final[0]["candidate_ids"]) == {
        candidate_id
        for item in classes
        for candidate_id in item["candidate_ids"]
    }


def test_grammar_exhaustion_trace_has_no_fitting_candidate() -> None:
    value = task(
        [{"input": [[1, 2], [3, 4]], "output": [[9, 9, 9], [9, 9, 9], [9, 9, 9]]}],
        [[[5]]],
        "exhausted",
    )

    result = grid_induction.run_public_task_v2_2(value, None, mechanistic=True)
    trace = result["mechanistic_trace"]

    assert result["predictions"] == [{"status": "GRAMMAR_EXHAUSTED", "prediction": None}]
    assert not [
        item
        for item in events(trace, "candidate_fit_decision")
        if item["decision"] == "FITS_ALL_DEMOS"
    ]
    assert events(trace, "final_decision")[0]["candidate_ids"] == []


def test_non_grid_mechanistic_mode_marks_frozen_delegate_as_opaque(monkeypatch: Any) -> None:
    expected = {"task_id": "text", "predictions": [{"status": "ACCEPTED", "prediction": "B"}]}

    def fake_delegate(value: object, engine: object) -> dict[str, object]:
        return expected

    monkeypatch.setattr(grid_induction, "run_public_task_v2", fake_delegate)
    value = task([{"input": "A", "output": "B"}], ["A"], "text")

    result = grid_induction.run_public_task_v2_2(value, object(), mechanistic=True)
    trace = result["mechanistic_trace"]
    boundary = events(trace, "delegate_boundary")

    assert without_trace(result) == expected
    assert boundary == [{
        **boundary[0],
        "visibility": "OPAQUE_FROZEN_CORE",
        "frozen_core_commit": "1d7c489bcdbff755d638b35ad47ce62bd4fe829d",
    }]
    assert events(trace, "final_decision")[0]["status"] == "DELEGATED"
    validate_trace(trace)
