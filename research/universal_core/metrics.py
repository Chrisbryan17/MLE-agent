from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .canonical import canonical_json_bytes, sha256_hex
from .contracts import FailureStatus


def _status_value(status: str | FailureStatus) -> str:
    return status.value if isinstance(status, FailureStatus) else str(status)


@dataclass(frozen=True)
class EvaluationMetrics:
    total_rows: int
    correct_rows: int
    attempted_rows: int
    raw_accuracy: float
    coverage: float
    attempted_accuracy: float
    coverage_adjusted_accuracy: float
    abstention_rate: float
    induction_success_rate: float
    verification_pass_rate: float
    deterministic_replay_rate: float
    status_counts: Mapping[str, int]
    task_family: str | None = None
    operation_family: str | None = None
    resource_usage: Mapping[str, Any] = field(default_factory=dict)
    synthesis_candidate_count: int = 0
    solver_trust_level: str | None = None
    first_attempt_id: str = "attempt-0001"

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_counts", dict(self.status_counts))
        object.__setattr__(self, "resource_usage", dict(self.resource_usage))

    def to_data(self) -> dict[str, Any]:
        task_breakdown = {}
        if self.task_family is not None:
            task_breakdown[self.task_family] = {
                "rows": self.total_rows,
                "correct": self.correct_rows,
                "accuracy": self.raw_accuracy,
                "coverage": self.coverage,
            }
        operation_breakdown = {}
        if self.operation_family is not None:
            operation_breakdown[self.operation_family] = {
                "rows": self.total_rows,
                "correct": self.correct_rows,
                "accuracy": self.raw_accuracy,
                "coverage": self.coverage,
            }
        return {
            "first_attempt_id": self.first_attempt_id,
            "total_rows": self.total_rows,
            "correct_rows": self.correct_rows,
            "attempted_rows": self.attempted_rows,
            "raw_accuracy": self.raw_accuracy,
            "coverage": self.coverage,
            "attempted_accuracy": self.attempted_accuracy,
            "coverage_adjusted_accuracy": self.coverage_adjusted_accuracy,
            "abstention_rate": self.abstention_rate,
            "induction_success_rate": self.induction_success_rate,
            "verification_pass_rate": self.verification_pass_rate,
            "deterministic_replay_rate": self.deterministic_replay_rate,
            "status_counts": dict(sorted(self.status_counts.items())),
            "task_family_breakdown": task_breakdown,
            "operation_family_breakdown": operation_breakdown,
            "resource_usage": dict(self.resource_usage),
            "synthesis_candidate_count": self.synthesis_candidate_count,
            "solver_trust_level": self.solver_trust_level,
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))


def compute_metrics(
    predictions: Sequence[Any],
    targets: Sequence[Any],
    statuses: Sequence[str | FailureStatus],
    *,
    induction_success: bool = True,
    verification_pass: bool = True,
    deterministic_replay: bool = True,
    task_family: str | None = None,
    operation_family: str | None = None,
    resource_usage: Mapping[str, Any] | None = None,
    synthesis_candidate_count: int = 0,
    solver_trust_level: str | None = None,
    first_attempt_id: str = "attempt-0001",
) -> EvaluationMetrics:
    if not (len(predictions) == len(targets) == len(statuses)):
        raise ValueError("predictions, targets, and statuses must have equal lengths")
    total = len(targets)
    if total == 0:
        raise ValueError("evaluation requires at least one target")
    normalized_statuses = tuple(_status_value(status) for status in statuses)
    attempted_flags = tuple(status == FailureStatus.SOLVED.value for status in normalized_statuses)
    attempted = sum(attempted_flags)
    correct = sum(
        attempted_flag and prediction == target
        for prediction, target, attempted_flag in zip(predictions, targets, attempted_flags)
    )
    raw_accuracy = correct / total
    coverage = attempted / total
    attempted_accuracy = correct / attempted if attempted else 0.0
    return EvaluationMetrics(
        total_rows=total,
        correct_rows=correct,
        attempted_rows=attempted,
        raw_accuracy=raw_accuracy,
        coverage=coverage,
        attempted_accuracy=attempted_accuracy,
        coverage_adjusted_accuracy=attempted_accuracy * coverage,
        abstention_rate=1.0 - coverage,
        induction_success_rate=1.0 if induction_success else 0.0,
        verification_pass_rate=1.0 if verification_pass else 0.0,
        deterministic_replay_rate=1.0 if deterministic_replay else 0.0,
        status_counts=Counter(normalized_statuses),
        task_family=task_family,
        operation_family=operation_family,
        resource_usage=resource_usage or {},
        synthesis_candidate_count=synthesis_candidate_count,
        solver_trust_level=solver_trust_level,
        first_attempt_id=first_attempt_id,
    )


def write_evaluation(attempt_dir: Path, metrics: EvaluationMetrics) -> Path:
    if attempt_dir.name != "attempt-0001" or attempt_dir.parent.name != "attempts":
        raise ValueError("attempt_dir must point to attempts/attempt-0001")
    output_path = attempt_dir.parent.parent / "evaluation.json"
    try:
        with output_path.open("xb") as handle:
            handle.write(canonical_json_bytes(metrics.to_data()))
    except FileExistsError as exc:
        raise FileExistsError(f"evaluation already exists: {output_path}") from exc
    return output_path
