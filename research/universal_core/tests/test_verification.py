from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from universal_core.contracts import Demonstration, OutputSchema, TaskPackage
from universal_core.induction import HeuristicProposalBackend
from universal_core.ir import Capability, TaskSpec, ValueType
from universal_core.templates import CandidateSolver, TemplateSynthesizer
from universal_core.verification import verify_candidate


@dataclass(frozen=True)
class MemorizingProgram:
    table: dict[str, str]

    def run(self, value: Any) -> Any:
        return self.table[value]

    def to_data(self) -> dict[str, Any]:
        return {"kind": "test_memorizer", "table": self.table}


def test_memorizing_candidate_fails_renaming_check() -> None:
    package = TaskPackage(
        "Return the corresponding symbol.",
        (
            Demonstration("alpha", "one"),
            Demonstration("beta", "two"),
            Demonstration("gamma", "three"),
        ),
        ("delta",),
        OutputSchema(kind="string"),
        {},
    )
    candidate = CandidateSolver(
        candidate_id="memorizer",
        spec=TaskSpec(ValueType.STRING, ValueType.STRING, capabilities=(Capability.MAP,), objective="map symbols"),
        program=MemorizingProgram({"alpha": "one", "beta": "two", "gamma": "three"}),
        trust_level="template",
        description_length=100,
    )
    report = verify_candidate(candidate, package)
    assert report.accepted is False
    assert any(check.name == "entity_renaming" and check.executed and not check.passed for check in report.checks)


def test_general_affine_candidate_passes_replay_and_fresh_values(affine_package) -> None:
    proposal = next(
        proposal
        for proposal in HeuristicProposalBackend().propose(
            affine_package.instructions,
            affine_package.demonstrations,
            affine_package.output_schema,
        )
        if proposal.program_data.get("template") == "affine"
    )
    candidate = TemplateSynthesizer().synthesize(proposal)
    report = verify_candidate(candidate, affine_package)
    assert report.demonstration_accuracy == 1.0
    assert report.deterministic is True
    assert report.accepted is True
    assert any(check.name == "bounded_counterexamples" and check.passed for check in report.checks)


def test_verified_sort_candidate_passes_nontrivial_checks(task_package) -> None:
    proposal = HeuristicProposalBackend().propose(
        task_package.instructions, task_package.demonstrations, task_package.output_schema
    )[0]
    report = verify_candidate(TemplateSynthesizer().synthesize(proposal), task_package)
    assert report.accepted is True
    assert report.nontrivial_pass_count >= 2
