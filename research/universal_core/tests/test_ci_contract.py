from __future__ import annotations

import json
from pathlib import Path

from .run_release_gates import evaluate_release_gates


REPO_ROOT = Path(__file__).parents[3]


def test_release_gate_report_is_machine_readable(tmp_path: Path) -> None:
    report = evaluate_release_gates(
        output_path=tmp_path / "release-gates.json",
        work_dir=tmp_path / "runs",
        exact_hidden_count=2,
        semantic_hidden_count=2,
    )
    assert report["protocol"] == "generated-private-style-holdout-v1"
    assert report["exact"]["rows"] == 40
    assert report["semantic"]["rows"] == 6
    assert report["overall"]["coverage"] == 1.0
    assert report["gates"]["all_passed"] is True
    assert json.loads((tmp_path / "release-gates.json").read_text()) == report


def test_workflow_contains_required_archive_and_replay_gates() -> None:
    workflow = (REPO_ROOT / ".github/workflows/universal-core-v1.yml").read_text()
    required = (
        "archive/universal-bbeh-dual-track-4520-2026-07-28",
        "a0c099a41c85f267ca6323235a019b2052107873",
        "python -m pytest research/universal_core/tests",
        "python -m universal_core.archive_guard",
        "python -m universal_core.tests.run_release_gates",
        "diff -ru artifacts/sample-a/attempts/attempt-0001",
        "universal-core-v1-evidence",
    )
    for token in required:
        assert token in workflow


def test_baseline_checkpoint_preserves_claim_boundary() -> None:
    checkpoint = (
        REPO_ROOT
        / "research/universal_core/checkpoints/2026-07-29/UNIVERSAL_CORE_V1_BASELINE.md"
    ).read_text()
    assert "synthetic private-style holdout" in checkpoint.lower()
    assert "not an independent private benchmark" in checkpoint.lower()
    assert "a0c099a41c85f267ca6323235a019b2052107873" in checkpoint
    assert "1,000" in checkpoint and "300" in checkpoint
