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
