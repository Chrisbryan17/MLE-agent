from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from universal_core.contracts import FailureStatus
from universal_core.ir import TaskSpec, ValueType
from universal_core.selection import select_candidate
from universal_core.templates import CandidateSolver
from universal_core.verification import VerificationCheck, VerificationReport


@dataclass(frozen=True)
class ConstantProgram:
    value: Any

    def run(self, row: Any) -> Any:
        return self.value

    def to_data(self) -> dict[str, Any]:
        return {"kind": "constant", "value": self.value}


def _candidate(identifier: str, trust: str, length: int, value: Any = 1) -> CandidateSolver:
    return CandidateSolver(
        identifier,
        TaskSpec(ValueType.INTEGER, ValueType.INTEGER, objective="constant"),
        ConstantProgram(value),
        trust,
        length,
    )


def _report(identifier: str, *, accepted: bool = True, differential: bool = True, nontrivial: int = 2) -> VerificationReport:
    checks = [
        VerificationCheck("demonstration_replay", True, {}),
        VerificationCheck("deterministic_replay", True, {}),
        VerificationCheck("output_schema", True, {}),
    ]
    checks.extend(VerificationCheck(f"nontrivial_{index}", True, {}, nontrivial=True) for index in range(nontrivial))
    if not differential:
        checks.append(VerificationCheck("differential_candidates", False, {"disagreements": ["other"]}, "disagreement", nontrivial=True))
    return VerificationReport(identifier, tuple(checks), 1.0, True, accepted)


def test_selector_prefers_trusted_shorter_verified_program() -> None:
    minilang = _candidate("mini", "minilang", 20)
    operator = _candidate("operator", "trusted_operator", 30)
    result = select_candidate([(minilang, _report("mini")), (operator, _report("operator"))])
    assert result.status is FailureStatus.SOLVED
    assert result.candidate is operator
    assert result.ranked_ids[0] == "operator"


def test_selector_uses_description_length_within_same_trust_tier() -> None:
    long = _candidate("long", "template", 100)
    short = _candidate("short", "template", 30)
    result = select_candidate([(long, _report("long")), (short, _report("short"))])
    assert result.candidate is short


def test_selector_abstains_when_candidates_have_unresolved_disagreement() -> None:
    left = _candidate("left", "template", 10, value=1)
    right = _candidate("right", "template", 10, value=2)
    result = select_candidate([
        (left, _report("left", accepted=False, differential=False)),
        (right, _report("right", accepted=False, differential=False)),
    ])
    assert result.status is FailureStatus.AMBIGUOUS_TASK
    assert result.candidate is None


def test_selector_distinguishes_no_proposals_from_failed_verification() -> None:
    assert select_candidate([]).status is FailureStatus.UNSUPPORTED_OPERATION
    candidate = _candidate("bad", "template", 10)
    bad_report = VerificationReport(
        "bad",
        (VerificationCheck("demonstration_replay", False, {}, "bad"),),
        0.0,
        True,
        False,
    )
    assert select_candidate([(candidate, bad_report)]).status is FailureStatus.VERIFICATION_FAILED
