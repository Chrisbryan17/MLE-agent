import json
from pathlib import Path

from universal_core.holonomy_v2.tests.run_v2_gates import run_gates


def test_full_gate_writes_verified_summary(tmp_path: Path) -> None:
    summary = run_gates(tmp_path)
    assert summary["ok"]
    assert summary["family"]["correct"] == 600
    assert summary["family"]["attempted"] == 600
    assert summary["mutation"]["rows"] == 400
    assert summary["mutation"]["raw_accuracy"] >= 0.95
    assert summary["replay"]["match"]
    assert summary["security"]["ok"]
    assert (tmp_path / "SHA256.json").is_file()
    written = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert written == summary
