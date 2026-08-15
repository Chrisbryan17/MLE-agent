from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from research.universal_core.holonomy_v2_2 import training_eval
from research.universal_core.holonomy_v2_2.mechanistic_trace import (
    TraceRecorder,
    validate_trace,
)


def write_task(path: Path, target: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "train": [{"input": [[0]], "output": [[target]]}],
            "test": [{"input": [[0]], "output": [[target]]}],
        }),
        encoding="utf-8",
    )


def build_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    write_task(vendor / "arc_agi_2" / "data" / "training" / "b.json", 2)
    write_task(vendor / "arc_agi_2" / "data" / "training" / "a.json", 1)
    return vendor


def accepted_trace(task_id: str, prediction: list[list[int]]) -> dict[str, object]:
    recorder = TraceRecorder(task_id)
    program = {"kind": "color_map", "mapping": {"0": prediction[0][0]}}
    program_ref = recorder.store(program)
    source_ref = recorder.store([[0]])
    target_ref = recorder.store(prediction)
    batch_ref = recorder.store([prediction])
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
        source_ref=source_ref,
        target_ref=target_ref,
        output_ref=target_ref,
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
        outcome="SUCCEEDED",
        input_ref=source_ref,
        output_ref=target_ref,
    )
    recorder.emit(
        "hidden_batch_decision",
        candidate_id="color_map:0000",
        candidate_kind="color_map",
        decision="COMPLETED",
        batch_ref=batch_ref,
    )
    recorder.emit(
        "equivalence_class",
        batch_ref=batch_ref,
        candidate_ids=["color_map:0000"],
        candidate_kinds=["color_map"],
    )
    recorder.emit(
        "final_decision",
        status="ACCEPTED",
        candidate_ids=["color_map:0000"],
        selected_candidate_id="color_map:0000",
    )
    return recorder.seal("ACCEPTED")


def runner_result(task_id: str, prediction: list[list[int]]) -> dict[str, object]:
    return {
        "task_id": task_id,
        "predictions": [{"status": "ACCEPTED", "prediction": prediction}],
    }


def test_training_run_writes_ordered_trace_files_and_digest_only_references(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    vendor = build_vendor(tmp_path)
    trace_dir = tmp_path / "traces"
    calls: list[tuple[str, bool]] = []

    def fake_run(
        task: dict[str, object],
        engine: object,
        *,
        mechanistic: bool = False,
    ) -> dict[str, object]:
        task_id = str(task["task_id"])
        calls.append((task_id, mechanistic))
        prediction = [[1 if task_id == "a" else 2]]
        result = runner_result(task_id, prediction)
        if mechanistic:
            result["mechanistic_trace"] = accepted_trace(task_id, prediction)
        return result

    monkeypatch.setattr(training_eval, "run_public_task_v2_2", fake_run)

    report = training_eval.run_training_corpus(
        vendor,
        engine=object(),
        run_label="training-mechanistic",
        candidate_commit="candidate-sha",
        mechanistic_dir=trace_dir,
        verify_parity=True,
    )

    assert calls == [("a", False), ("a", True), ("b", False), ("b", True)]
    assert [item["task_id"] for item in report["reports"]] == ["a", "b"]
    assert sorted(path.name for path in trace_dir.glob("*.json")) == [
        "a.json",
        "b.json",
        "diagnosis.json",
    ]
    assert report["mechanistic"]["trace_count"] == 2
    assert report["mechanistic"]["parity_count"] == 2
    assert report["mechanistic"]["diagnosis_path"] == "diagnosis.json"
    for item in report["reports"]:
        reference = item["mechanistic_trace"]
        assert set(reference) == {
            "path",
            "trace_digest",
            "envelope_digest",
            "event_count",
            "terminal_status",
        }
        assert "mechanistic_trace" not in item["raw_result"]
        trace = json.loads((trace_dir / reference["path"]).read_text(encoding="utf-8"))
        validate_trace(trace)
        assert trace["trace_digest"] == reference["trace_digest"]
        assert trace["envelope_digest"] == reference["envelope_digest"]
    diagnosis = json.loads((trace_dir / "diagnosis.json").read_text(encoding="utf-8"))
    assert diagnosis["trace_count"] == 2
    assert report["mechanistic"]["diagnosis_digest"] == diagnosis["diagnosis_digest"]


def test_training_run_fails_closed_on_mechanistic_parity_mismatch(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    vendor = build_vendor(tmp_path)

    def fake_run(
        task: dict[str, object],
        engine: object,
        *,
        mechanistic: bool = False,
    ) -> dict[str, object]:
        task_id = str(task["task_id"])
        compact_prediction = [[1 if task_id == "a" else 2]]
        prediction = [[9]] if mechanistic else compact_prediction
        result = runner_result(task_id, prediction)
        if mechanistic:
            result["mechanistic_trace"] = accepted_trace(task_id, prediction)
        return result

    monkeypatch.setattr(training_eval, "run_public_task_v2_2", fake_run)

    with pytest.raises(RuntimeError, match="mechanistic parity failure for task a"):
        training_eval.run_training_corpus(
            vendor,
            engine=object(),
            run_label="parity-failure",
            mechanistic_dir=tmp_path / "traces",
            verify_parity=True,
        )


def test_trace_files_do_not_embed_the_aggregate_report_or_scoring_metrics(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    vendor = build_vendor(tmp_path)
    trace_dir = tmp_path / "traces"

    def fake_run(
        task: dict[str, object],
        engine: object,
        *,
        mechanistic: bool = False,
    ) -> dict[str, object]:
        task_id = str(task["task_id"])
        prediction = [[1 if task_id == "a" else 2]]
        result = runner_result(task_id, prediction)
        if mechanistic:
            result["mechanistic_trace"] = accepted_trace(task_id, prediction)
        return result

    monkeypatch.setattr(training_eval, "run_public_task_v2_2", fake_run)
    training_eval.run_training_corpus(
        vendor,
        engine=object(),
        run_label="no-score-leak",
        mechanistic_dir=trace_dir,
        verify_parity=True,
    )

    for path in (trace_dir / "a.json", trace_dir / "b.json"):
        text = path.read_text(encoding="utf-8")
        assert '"metrics"' not in text
        assert '"correct"' not in text
        assert '"raw_accuracy"' not in text
        assert '"report_digest"' not in text
