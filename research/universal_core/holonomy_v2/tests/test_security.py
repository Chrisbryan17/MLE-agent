from pathlib import Path

from universal_core.holonomy_v2.security import scan_tree


def test_dynamic_execution_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("def f(x):\n    return eval(x)\n", encoding="utf-8")
    report = scan_tree(tmp_path)
    assert not report.ok
    assert any(item.code == "DYNAMIC_EXECUTION" for item in report.findings)


def test_regression_import_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "from universal_core.holonomy_v2.tests.regression import data\n",
        encoding="utf-8",
    )
    report = scan_tree(tmp_path)
    assert any(item.code == "TEST_IMPORT" for item in report.findings)


def test_task_routing_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "def f(task_id):\n    if task_id == 'family-a':\n        return 1\n",
        encoding="utf-8",
    )
    report = scan_tree(tmp_path)
    assert any(item.code == "TASK_ROUTING" for item in report.findings)


def test_current_production_tree_is_clean() -> None:
    root = Path(__file__).parents[1]
    report = scan_tree(root)
    assert report.ok, report.to_data()
