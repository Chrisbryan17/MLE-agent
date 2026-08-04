from __future__ import annotations

from research.universal_core.holonomy_v2_2.mechanistic_trace import TraceRecorder
from research.universal_core.holonomy_v2_2.trace_diagnosis import build_trace_diagnosis


def accepted_trace(task_id: str) -> dict[str, object]:
    recorder = TraceRecorder(task_id)
    program = {"kind": "identity"}
    program_ref = recorder.store(program)
    grid_ref = recorder.store([[1]])
    batch_ref = recorder.store([[[1]]])
    recorder.emit("run_start", version="test", demo_count=1, hidden_count=1, mode="GRID")
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        generator_ordinal=0,
        candidate_kind="identity",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit(
        "demo_execution",
        candidate_id="fixed:0000",
        candidate_kind="identity",
        demo_index=0,
        outcome="MATCH",
        source_ref=grid_ref,
        target_ref=grid_ref,
        output_ref=grid_ref,
    )
    recorder.emit(
        "candidate_fit_decision",
        candidate_id="fixed:0000",
        candidate_kind="identity",
        decision="FITS_ALL_DEMOS",
    )
    recorder.emit(
        "hidden_execution",
        candidate_id="fixed:0000",
        candidate_kind="identity",
        hidden_index=0,
        outcome="SUCCEEDED",
        input_ref=grid_ref,
        output_ref=grid_ref,
    )
    recorder.emit(
        "hidden_batch_decision",
        candidate_id="fixed:0000",
        candidate_kind="identity",
        decision="COMPLETED",
        batch_ref=batch_ref,
    )
    recorder.emit(
        "equivalence_class",
        batch_ref=batch_ref,
        candidate_ids=["fixed:0000"],
        candidate_kinds=["identity"],
    )
    recorder.emit(
        "final_decision",
        status="ACCEPTED",
        candidate_ids=["fixed:0000"],
        selected_candidate_id="fixed:0000",
    )
    return recorder.seal("ACCEPTED")


def failed_trace(task_id: str) -> dict[str, object]:
    recorder = TraceRecorder(task_id)
    program = {"kind": "color_map", "mapping": {"0": 1}}
    program_ref = recorder.store(program)
    grid_ref = recorder.store([[0]])
    recorder.emit("run_start", version="test", demo_count=1, hidden_count=1, mode="GRID")
    recorder.emit(
        "candidate_proposed",
        candidate_id="color_map:0000",
        generator="color_map",
        generator_ordinal=0,
        candidate_kind="color_map",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit(
        "demo_execution",
        candidate_id="color_map:0000",
        candidate_kind="color_map",
        demo_index=0,
        outcome="MATCH",
        source_ref=grid_ref,
        target_ref=grid_ref,
        output_ref=grid_ref,
    )
    recorder.emit(
        "candidate_fit_decision",
        candidate_id="color_map:0000",
        candidate_kind="color_map",
        decision="FITS_ALL_DEMOS",
    )
    recorder.emit(
        "hidden_execution",
        candidate_id="color_map:0000",
        candidate_kind="color_map",
        hidden_index=0,
        outcome="FAILED",
        input_ref=grid_ref,
        exception_type="KeyError",
        exception_message="'unmapped grid cell'",
    )
    recorder.emit(
        "hidden_batch_decision",
        candidate_id="color_map:0000",
        candidate_kind="color_map",
        decision="FAILED",
    )
    recorder.emit(
        "final_decision",
        status="EXECUTION_FAILED",
        candidate_ids=["color_map:0000"],
    )
    return recorder.seal("EXECUTION_FAILED")


def test_diagnosis_counts_terminal_decisions_selected_kinds_and_hidden_failures() -> None:
    diagnosis = build_trace_diagnosis([
        accepted_trace("accepted"),
        failed_trace("failed"),
    ])

    assert diagnosis["trace_count"] == 2
    assert diagnosis["terminal_status_counts"] == {
        "ACCEPTED": 1,
        "EXECUTION_FAILED": 1,
    }
    assert diagnosis["accepted_selected_kind_counts"] == {"identity": 1}
    assert diagnosis["hidden_failure_counts"] == {
        "color_map": {"KeyError": 1},
    }
    assert diagnosis["candidate_fit_counts"]["color_map"] == {
        "FITS_ALL_DEMOS": 1,
    }
    assert len(diagnosis["diagnosis_digest"]) == 64


def test_diagnosis_is_deterministic_across_input_order() -> None:
    first = build_trace_diagnosis([accepted_trace("a"), failed_trace("b")])
    second = build_trace_diagnosis([failed_trace("b"), accepted_trace("a")])

    assert first == second
