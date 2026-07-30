from __future__ import annotations

import json

import pytest

from universal_core.metrics import compute_metrics, write_evaluation


def test_metrics_report_accuracy_and_coverage_separately() -> None:
    metrics = compute_metrics(
        predictions=("a", None, "c"),
        targets=("a", "b", "x"),
        statuses=("SOLVED", "LOW_CONFIDENCE", "SOLVED"),
    )
    assert metrics.raw_accuracy == pytest.approx(1 / 3)
    assert metrics.coverage == pytest.approx(2 / 3)
    assert metrics.attempted_accuracy == pytest.approx(1 / 2)
    assert metrics.coverage_adjusted_accuracy == pytest.approx(1 / 3)
    assert metrics.abstention_rate == pytest.approx(1 / 3)


def test_metrics_capture_pipeline_and_resource_evidence() -> None:
    metrics = compute_metrics(
        predictions=(1, 2),
        targets=(1, 2),
        statuses=("SOLVED", "SOLVED"),
        induction_success=True,
        verification_pass=True,
        deterministic_replay=True,
        task_family="affine",
        operation_family="EVALUATE_EXPRESSION",
        resource_usage={"runtime_ms": 2.5, "peak_memory_bytes": 1024},
        synthesis_candidate_count=3,
        solver_trust_level="template",
    )
    data = metrics.to_data()
    assert data["raw_accuracy"] == 1.0
    assert data["deterministic_replay_rate"] == 1.0
    assert data["resource_usage"]["peak_memory_bytes"] == 1024
    assert data["synthesis_candidate_count"] == 3


def test_evaluation_is_written_beside_not_inside_sealed_attempt(tmp_path) -> None:
    attempt = tmp_path / "attempts" / "attempt-0001"
    attempt.mkdir(parents=True)
    (attempt / "immutable.txt").write_text("sealed\n")
    metrics = compute_metrics((1,), (1,), ("SOLVED",))
    path = write_evaluation(attempt, metrics)
    assert path == tmp_path / "evaluation.json"
    assert (attempt / "immutable.txt").read_text() == "sealed\n"
    assert json.loads(path.read_text())["raw_accuracy"] == 1.0
