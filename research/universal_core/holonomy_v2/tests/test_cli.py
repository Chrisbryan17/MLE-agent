import json
from pathlib import Path

from universal_core.holonomy_v2.cli import main


def _task(path: Path) -> None:
    path.write_text(json.dumps({
        "task_id": "opaque",
        "instructions": "Return 2*n+1.",
        "demonstrations": [
            {"input": 1, "output": 3},
            {"input": 2, "output": 5},
            {"input": 3, "output": 7},
        ],
        "hidden_inputs": [4, 5],
    }), encoding="utf-8")


def test_predict_command_writes_sealed_batch(tmp_path: Path) -> None:
    task = tmp_path / "task.json"
    out = tmp_path / "out.json"
    _task(task)
    assert main(["predict", "--task", str(task), "--output", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [item["prediction"] for item in data["predictions"]] == [9, 11]
    assert data["freeze_digest"]


def test_scan_command_reports_clean_tree(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "ok.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    out = tmp_path / "scan.json"
    assert main(["scan", "--root", str(root), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["ok"]
