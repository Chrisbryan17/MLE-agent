from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.universal_core.holonomy_v2_2.mechanistic_trace import (
    TraceRecorder,
    validate_trace,
    write_trace,
)


def complete_trace(task_id: str = "alpha") -> dict[str, object]:
    recorder = TraceRecorder(task_id)
    program_ref = recorder.store({"kind": "identity"})
    grid_ref = recorder.store([[1]])
    batch_ref = recorder.store([[[1]]])
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit(
        "demo_execution",
        candidate_id="fixed:0000",
        demo_index=0,
        outcome="MATCH",
        output_ref=grid_ref,
        target_ref=grid_ref,
    )
    recorder.emit(
        "candidate_fit_decision",
        candidate_id="fixed:0000",
        decision="FITS_ALL_DEMOS",
    )
    recorder.emit(
        "hidden_execution",
        candidate_id="fixed:0000",
        hidden_index=0,
        outcome="SUCCEEDED",
        output_ref=grid_ref,
    )
    recorder.emit(
        "hidden_batch_decision",
        candidate_id="fixed:0000",
        decision="COMPLETED",
        batch_ref=batch_ref,
    )
    recorder.emit(
        "equivalence_class",
        batch_ref=batch_ref,
        candidate_ids=["fixed:0000"],
    )
    recorder.emit(
        "final_decision",
        status="ACCEPTED",
        candidate_ids=["fixed:0000"],
    )
    return recorder.seal("ACCEPTED")


def test_trace_is_deterministic_and_task_id_independent() -> None:
    first = complete_trace("alpha")
    second = complete_trace("beta")

    assert first["trace_digest"] == second["trace_digest"]
    assert first["envelope_digest"] != second["envelope_digest"]
    assert json.dumps(first, sort_keys=True) == json.dumps(complete_trace("alpha"), sort_keys=True)


def test_validator_rejects_missing_candidate_terminal_event() -> None:
    recorder = TraceRecorder("bad")
    program_ref = recorder.store({"kind": "identity"})
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit("final_decision", status="GRAMMAR_EXHAUSTED", candidate_ids=[])

    with pytest.raises(ValueError, match="terminal demonstration decision"):
        recorder.seal("GRAMMAR_EXHAUSTED")


def test_validator_rejects_missing_hidden_terminal_event() -> None:
    recorder = TraceRecorder("bad-hidden")
    program_ref = recorder.store({"kind": "identity"})
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit(
        "candidate_fit_decision",
        candidate_id="fixed:0000",
        decision="FITS_ALL_DEMOS",
    )
    recorder.emit("final_decision", status="EXECUTION_FAILED", candidate_ids=["fixed:0000"])

    with pytest.raises(ValueError, match="terminal hidden-batch decision"):
        recorder.seal("EXECUTION_FAILED")


def test_validator_rejects_unknown_object_reference() -> None:
    trace = complete_trace()
    trace["events"][1]["output_ref"] = "0" * 64

    with pytest.raises(ValueError, match="unknown object reference"):
        validate_trace(trace)


def test_store_rejects_non_json_values() -> None:
    recorder = TraceRecorder("unsafe")

    with pytest.raises(TypeError, match="JSON-safe"):
        recorder.store({"bad": object()})


def test_write_trace_emits_canonical_json(tmp_path: Path) -> None:
    trace = complete_trace()
    path = write_trace(trace, tmp_path / "trace.json")

    assert path.read_text(encoding="utf-8").endswith("\n")
    validate_trace(json.loads(path.read_text(encoding="utf-8")))
