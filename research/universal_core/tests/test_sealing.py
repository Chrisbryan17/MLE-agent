from __future__ import annotations

import json

import pytest

from universal_core.contracts import FailureStatus, PredictionRow
from universal_core.induction import HeuristicProposalBackend
from universal_core.sealing import (
    AttemptExistsError,
    freeze_solver,
    verify_attempt,
    write_first_attempt,
)
from universal_core.templates import TemplateSynthesizer
from universal_core.verification import verify_candidate


def _manifest(affine_package):
    proposal = next(
        p for p in HeuristicProposalBackend().propose(
            affine_package.instructions, affine_package.demonstrations, affine_package.output_schema
        ) if p.program_data.get("template") == "affine"
    )
    candidate = TemplateSynthesizer().synthesize(proposal)
    report = verify_candidate(candidate, affine_package)
    return freeze_solver(
        affine_package,
        candidate,
        report,
        runtime_config={"python": "3.12"},
        dependencies={"universal_core": "0.1.0"},
        seeds={"synthesis": 0},
        limits={"max_steps": 10_000},
        timestamp="2026-07-29T00:00:00Z",
    )


def _predictions():
    return (
        PredictionRow(0, 11, FailureStatus.SOLVED, 0.99, 0.1),
        PredictionRow(1, 26, FailureStatus.SOLVED, 0.99, 0.1),
    )


def test_first_attempt_cannot_be_overwritten(tmp_path, affine_package) -> None:
    manifest = _manifest(affine_package)
    write_first_attempt(tmp_path, manifest, _predictions())
    with pytest.raises(AttemptExistsError):
        write_first_attempt(tmp_path, manifest, _predictions())


def test_attempt_verification_detects_mutation(tmp_path, affine_package) -> None:
    attempt = write_first_attempt(tmp_path, _manifest(affine_package), _predictions())
    (attempt / "predictions.json").write_text("{}\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_attempt(attempt)


def test_sealed_attempt_verifies_and_records_prediction_digest(tmp_path, affine_package) -> None:
    manifest = _manifest(affine_package)
    attempt = write_first_attempt(tmp_path, manifest, _predictions())
    verify_attempt(attempt)
    attempt_data = json.loads((attempt / "ATTEMPT.json").read_text())
    assert attempt_data["freeze_digest"] == manifest.digest
    assert len(attempt_data["prediction_digest"]) == 64
    assert set(json.loads((attempt / "SHA256.json").read_text())) == {
        "ATTEMPT.json", "manifest.json", "predictions.json"
    }
