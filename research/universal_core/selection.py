from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contracts import FailureStatus
from .templates import CandidateSolver
from .verification import VerificationReport


@dataclass(frozen=True)
class SelectionResult:
    status: FailureStatus
    candidate: CandidateSolver | None
    reason: str
    ranked_ids: tuple[str, ...] = ()


_TRUST_RANK = {
    "trusted_operator": 0,
    "template": 1,
    "minilang": 2,
}


def _rank_key(item: tuple[CandidateSolver, VerificationReport]) -> tuple[object, ...]:
    candidate, report = item
    return (
        -report.pass_count,
        _TRUST_RANK.get(candidate.trust_level, 99),
        -report.demonstration_accuracy,
        candidate.description_length,
        candidate.measured_runtime_ms,
        candidate.candidate_id,
    )


def _has_differential_failure(report: VerificationReport) -> bool:
    return any(
        check.name == "differential_candidates" and check.executed and not check.passed
        for check in report.checks
    )


def _has_only_insufficient_evidence(report: VerificationReport) -> bool:
    essentials = {"demonstration_replay", "deterministic_replay", "output_schema"}
    essential_checks = [check for check in report.checks if check.name in essentials]
    no_executed_failure = not any(check.executed and not check.passed for check in report.checks)
    return bool(essential_checks) and all(check.passed for check in essential_checks) and no_executed_failure and report.nontrivial_pass_count < 2


def select_candidate(
    candidates: Sequence[tuple[CandidateSolver, VerificationReport]],
) -> SelectionResult:
    if not candidates:
        return SelectionResult(
            FailureStatus.UNSUPPORTED_OPERATION,
            None,
            "no candidate solver was synthesized",
        )
    for candidate, report in candidates:
        if candidate.candidate_id != report.candidate_id:
            raise ValueError(
                f"candidate/report identity mismatch: {candidate.candidate_id} != {report.candidate_id}"
            )

    accepted = sorted((item for item in candidates if item[1].accepted), key=_rank_key)
    ranked_all = tuple(candidate.candidate_id for candidate, _ in sorted(candidates, key=_rank_key))
    if accepted:
        candidate, _ = accepted[0]
        return SelectionResult(
            FailureStatus.SOLVED,
            candidate,
            "selected highest-ranked verified candidate",
            ranked_all,
        )

    if any(_has_differential_failure(report) for _, report in candidates):
        return SelectionResult(
            FailureStatus.AMBIGUOUS_TASK,
            None,
            "candidate solvers have unresolved differential disagreements",
            ranked_all,
        )

    if all(_has_only_insufficient_evidence(report) for _, report in candidates):
        return SelectionResult(
            FailureStatus.INSUFFICIENT_DEMONSTRATIONS,
            None,
            "available demonstrations did not support two nontrivial verification modes",
            ranked_all,
        )

    return SelectionResult(
        FailureStatus.VERIFICATION_FAILED,
        None,
        "all synthesized candidates failed verification",
        ranked_all,
    )
