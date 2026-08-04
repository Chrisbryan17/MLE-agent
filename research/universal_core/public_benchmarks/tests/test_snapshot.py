from __future__ import annotations

import json
import pathlib

import pytest

from research.universal_core.public_benchmarks import snapshot


def write(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_valid_grid_enforces_arc_contract() -> None:
    assert snapshot.valid_grid([[0, 1], [2, 9]])
    assert not snapshot.valid_grid([])
    assert not snapshot.valid_grid([[0], [1, 2]])
    assert not snapshot.valid_grid([[10]])
    assert not snapshot.valid_grid([[True]])


def test_bbeh_counter_requires_input_and_target(tmp_path: pathlib.Path) -> None:
    write(tmp_path / "task-a" / "task.json", {"examples": [{"input": "q", "target": "a"}]})
    assert snapshot.count_bbeh(tmp_path) == (1, 1, ["task-a"])
    write(tmp_path / "task-b" / "task.json", {"examples": [{"input": "q"}]})
    with pytest.raises(RuntimeError, match="malformed"):
        snapshot.count_bbeh(tmp_path)


def test_bbeh_mini_counter_requires_input_and_target(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.json"
    write(
        path,
        {
            "examples": [
                {"input": "q1", "target": "a1"},
                {"input": "q2", "target": "a2"},
            ]
        },
    )
    assert snapshot.count_bbeh_mini(path) == 2
    write(path, {"examples": [{"input": "q"}]})
    with pytest.raises(RuntimeError, match="malformed"):
        snapshot.count_bbeh_mini(path)


def test_livebench_accepts_category_specific_answer_fields(tmp_path: pathlib.Path) -> None:
    repositories = [
        "livebench/coding",
        "livebench/data_analysis",
        "livebench/instruction_following",
        "livebench/language",
        "livebench/math",
        "livebench/reasoning",
    ]
    revisions = {}
    for index, repo_id in enumerate(repositories):
        category = repo_id.split("/", 1)[1]
        row = {
            "question_id": f"q-{index}",
            "task": f"task-{index}",
            "turns": ["prompt"],
            "livebench_release_date": "2026-06-25",
        }
        path = tmp_path / "questions" / f"{category}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        revisions[repo_id] = {"revision": f"sha-{index}", "rows": 1}
    write(tmp_path / "DATASET_REVISIONS.json", revisions)
    result = snapshot.verify_livebench(
        tmp_path,
        {
            "commit": "harness-sha",
            "public_release_ceiling": "2026-06-25",
            "dataset_repositories": repositories,
        },
    )
    assert result["total_rows"] == 6


def test_inventory_is_stable_and_excludes_manifest(tmp_path: pathlib.Path) -> None:
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / snapshot.MANIFEST_NAME).write_text("{}", encoding="utf-8")
    inventory = snapshot.file_inventory(tmp_path)
    assert [item["path"] for item in inventory] == ["a.txt", "b.txt"]
    assert all(len(item["sha256"]) == 64 for item in inventory)


def test_snapshot_creation_is_one_shot(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / snapshot.MANIFEST_NAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(snapshot, "load_lock", lambda: {})
    with pytest.raises(RuntimeError, match="already exists"):
        snapshot.fetch_all(vendor)
