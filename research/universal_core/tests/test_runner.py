from __future__ import annotations

import json
from pathlib import Path

from universal_core.contracts import FailureStatus
from universal_core.normalizer import normalize_task_payload
from universal_core.runner import UniversalCoreRunner
from universal_core.sealing import verify_attempt


def test_runner_induces_freezes_and_executes_unseen_sort_rows(task_package, tmp_path) -> None:
    result = UniversalCoreRunner.default().run(task_package, tmp_path)
    assert result.status is FailureStatus.SOLVED
    assert result.predictions[0].prediction == [["y", 5], ["x", 7]]
    assert len(result.solver_digest or "") == 64
    attempt = tmp_path / "attempts" / "attempt-0001"
    assert (attempt / "SHA256.json").exists()
    verify_attempt(attempt)
    manifest = json.loads((attempt / "manifest.json").read_text())
    assert manifest["package_digest"] == task_package.package_digest


def test_runner_seals_abstention_for_unsupported_task(tmp_path) -> None:
    package = normalize_task_payload({
        "instructions": "Invent a poem with an unknowable hidden aesthetic.",
        "demonstrations": [
            {"input": {"topic": "a"}, "output": {"verse": "one"}},
            {"input": {"topic": "b"}, "output": {"verse": "two"}},
            {"input": {"topic": "c"}, "output": {"verse": "three"}}
        ],
        "hidden_inputs": [{"topic": "x"}],
        "output_schema": {"kind": "record"}
    })
    result = UniversalCoreRunner.default().run(package, tmp_path)
    assert result.status in {FailureStatus.UNSUPPORTED_OPERATION, FailureStatus.VERIFICATION_FAILED}
    assert result.predictions[0].prediction is None
    verify_attempt(tmp_path / "attempts" / "attempt-0001")


def test_cli_fixture_is_a_valid_private_package() -> None:
    payload = json.loads((Path(__file__).parent / "fixtures" / "sort_records.json").read_text())
    package = normalize_task_payload(payload)
    assert len(package.demonstrations) == 3
    assert len(package.hidden_inputs) == 2


def test_cli_runs_fixture_and_returns_zero(tmp_path, capsys) -> None:
    from universal_core.cli import main

    fixture = Path(__file__).parent / "fixtures" / "sort_records.json"
    assert main(["run", "--task", str(fixture), "--output", str(tmp_path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "SOLVED"
    assert summary["solved_rows"] == 2
