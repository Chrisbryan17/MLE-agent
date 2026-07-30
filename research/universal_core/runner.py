from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import __version__
from .contracts import AttemptResult, FailureStatus, PredictionRow, TaskPackage
from .induction import HeuristicProposalBackend, ProposalBackend, build_induction_view
from .sealing import (
    freeze_solver,
    verify_attempt,
    write_first_attempt,
    write_unresolved_attempt,
)
from .selection import select_candidate
from .templates import CandidateSolver, TemplateSynthesizer
from .verification import VerificationReport, output_matches_schema, verify_candidate


@dataclass(frozen=True)
class UniversalCoreRunner:
    backends: tuple[ProposalBackend, ...]
    synthesizer: TemplateSynthesizer = field(default_factory=TemplateSynthesizer)
    runtime_config: Mapping[str, Any] = field(default_factory=dict)
    dependencies: Mapping[str, str] = field(default_factory=dict)
    seeds: Mapping[str, int] = field(default_factory=lambda: {"synthesis": 0})
    limits: Mapping[str, Any] = field(default_factory=lambda: {
        "max_steps": 10_000,
        "max_loop_items": 1_000,
        "max_output_bytes": 1_000_000,
        "max_depth": 64,
    })
    timestamp: str = "1970-01-01T00:00:00Z"

    def __post_init__(self) -> None:
        object.__setattr__(self, "backends", tuple(self.backends))
        object.__setattr__(self, "runtime_config", dict(self.runtime_config))
        object.__setattr__(self, "dependencies", dict(self.dependencies))
        object.__setattr__(self, "seeds", dict(self.seeds))
        object.__setattr__(self, "limits", dict(self.limits))

    @classmethod
    def default(cls) -> "UniversalCoreRunner":
        return cls(
            backends=(HeuristicProposalBackend(),),
            runtime_config={
                "python_version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "pipeline": "universal-core-v1",
            },
            dependencies={"universal_core": __version__},
        )

    def _propose(self, package: TaskPackage) -> tuple[list[Any], list[str]]:
        view = build_induction_view(package)
        proposals: list[Any] = []
        errors: list[str] = []
        for backend in self.backends:
            try:
                proposals.extend(
                    backend.propose(
                        view["instructions"],
                        package.demonstrations,
                        package.output_schema,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - backend failure is typed audit evidence
                errors.append(f"{type(backend).__name__}: {type(exc).__name__}: {exc}")
        unique = {proposal.proposal_id: proposal for proposal in proposals}
        return [unique[key] for key in sorted(unique)], errors

    def run(self, package: TaskPackage, output_root: Path) -> AttemptResult:
        proposals, backend_errors = self._propose(package)
        candidates: list[CandidateSolver] = []
        synthesis_errors: list[str] = []
        for proposal in proposals:
            try:
                candidates.append(self.synthesizer.synthesize(proposal))
            except Exception as exc:  # noqa: BLE001
                synthesis_errors.append(f"{proposal.proposal_id}: {type(exc).__name__}: {exc}")

        reports: list[VerificationReport] = [verify_candidate(candidate, package) for candidate in candidates]
        selection = select_candidate(list(zip(candidates, reports)))
        audit = {
            "induction_view_digest": package.package_digest,
            "proposal_count": len(proposals),
            "candidate_count": len(candidates),
            "backend_errors": backend_errors,
            "synthesis_errors": synthesis_errors,
            "selection_reason": selection.reason,
            "ranked_candidate_ids": list(selection.ranked_ids),
            "verification": [report.to_data() for report in reports],
        }

        if selection.candidate is None:
            predictions = tuple(
                PredictionRow(
                    index=index,
                    prediction=None,
                    status=selection.status,
                    confidence=0.0,
                    runtime_ms=0.0,
                    error=selection.reason,
                )
                for index, _ in enumerate(package.hidden_inputs)
            )
            attempt = write_unresolved_attempt(
                output_root,
                package_digest=package.package_digest,
                status=selection.status.value,
                reason=selection.reason,
                predictions=predictions,
                timestamp=self.timestamp,
                audit=audit,
            )
            verify_attempt(attempt)
            attempt_data = json.loads((attempt / "ATTEMPT.json").read_text(encoding="utf-8"))
            return AttemptResult(
                status=selection.status,
                predictions=predictions,
                package_digest=package.package_digest,
                solver_digest=None,
                prediction_digest=attempt_data["prediction_digest"],
                attempt_id="attempt-0001",
                audit_path=str(attempt),
                details=audit,
            )

        candidate = selection.candidate
        report = next(report for report in reports if report.candidate_id == candidate.candidate_id)
        manifest = freeze_solver(
            package,
            candidate,
            report,
            runtime_config=self.runtime_config,
            dependencies=self.dependencies,
            seeds=self.seeds,
            limits=self.limits,
            timestamp=self.timestamp,
        )

        prediction_rows: list[PredictionRow] = []
        for index, row in enumerate(package.hidden_inputs):
            try:
                prediction = candidate.run(row)
                runtime_ms = 0.0
                if output_matches_schema(package.output_schema, prediction):
                    status = FailureStatus.SOLVED
                    error = None
                else:
                    status = FailureStatus.OUTPUT_SCHEMA_CONFLICT
                    error = f"prediction does not match output schema {package.output_schema.kind}"
                    prediction = None
            except Exception as exc:  # noqa: BLE001 - row failures must be sealed, not escape
                runtime_ms = 0.0
                prediction = None
                status = FailureStatus.EXECUTION_FAILED
                error = f"{type(exc).__name__}: {exc}"
            prediction_rows.append(
                PredictionRow(
                    index=index,
                    prediction=prediction,
                    status=status,
                    confidence=candidate.confidence if status is FailureStatus.SOLVED else 0.0,
                    runtime_ms=runtime_ms,
                    error=error,
                )
            )

        predictions = tuple(prediction_rows)
        attempt = write_first_attempt(output_root, manifest, predictions)
        verify_attempt(attempt)
        attempt_data = json.loads((attempt / "ATTEMPT.json").read_text(encoding="utf-8"))
        overall_status = next(
            (row.status for row in predictions if row.status is not FailureStatus.SOLVED),
            FailureStatus.SOLVED,
        )
        return AttemptResult(
            status=overall_status,
            predictions=predictions,
            package_digest=package.package_digest,
            solver_digest=manifest.solver_digest,
            prediction_digest=attempt_data["prediction_digest"],
            attempt_id="attempt-0001",
            audit_path=str(attempt),
            details=audit,
        )
