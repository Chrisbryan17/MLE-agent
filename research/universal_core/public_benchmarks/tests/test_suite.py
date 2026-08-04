from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.universal_core.public_benchmarks import suite


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def build_vendor(tmp_path: Path) -> Path:
    vendor = tmp_path / "nested" / "vendor"
    write_json(vendor / "SNAPSHOT_MANIFEST.json", {"inventory_digest": "abc"})
    write_json(
        vendor / "arc_agi_2" / "data" / "evaluation" / "b.json",
        {"train": [{"input": [[0]], "output": [[1]]}], "test": [{"input": [[2]], "output": [[3]]}]},
    )
    write_json(
        vendor / "arc_agi_2" / "data" / "evaluation" / "a.json",
        {"train": [{"input": [[1]], "output": [[2]]}], "test": [{"input": [[3]], "output": [[4]]}]},
    )
    write_json(
        vendor / "bbeh" / "full" / "task-b" / "task.json",
        {"examples": [{"input": "b0", "target": "B0"}, {"input": "b1", "target": "B1"}]},
    )
    write_json(
        vendor / "bbeh" / "full" / "task-a" / "task.json",
        {"examples": [{"input": "a0", "target": "A0"}, {"input": "a1", "target": "A1"}]},
    )
    write_jsonl(
        vendor / "livebench" / "questions" / "reasoning.jsonl",
        [
            {"question_id": "q2", "category": "reasoning", "task": "spatial", "turns": ["p2"], "ground_truth": "C"},
            {"question_id": "q1", "category": "reasoning", "task": "spatial", "turns": ["p1"], "ground_truth": "B"},
            {"question_id": "q3", "category": "reasoning", "task": "zebra", "turns": ["p3"], "ground_truth": "D"},
        ],
    )
    write_jsonl(
        vendor / "livebench" / "questions" / "coding.jsonl",
        [
            {"question_id": "c1", "category": "coding", "task": "code", "turns": ["code prompt"]},
        ],
    )
    return vendor


def test_locate_vendor_finds_exact_manifest_parent(tmp_path: Path) -> None:
    vendor = build_vendor(tmp_path)
    assert suite.locate_vendor(tmp_path) == vendor


def test_locate_vendor_rejects_multiple_manifests(tmp_path: Path) -> None:
    build_vendor(tmp_path)
    write_json(tmp_path / "other" / "SNAPSHOT_MANIFEST.json", {})
    with pytest.raises(ValueError, match="exactly one"):
        suite.locate_vendor(tmp_path)


def test_loaders_are_deterministically_ordered(tmp_path: Path) -> None:
    vendor = build_vendor(tmp_path)

    arc = suite.load_arc_tasks(vendor, "evaluation")
    bbeh = suite.load_bbeh_tasks(vendor)
    livebench = suite.load_livebench(vendor)

    assert [task_id for task_id, _ in arc] == ["a", "b"]
    assert [task_id for task_id, _ in bbeh] == ["task-a", "task-b"]
    assert list(livebench.groups) == ["reasoning:spatial", "reasoning:zebra"]
    assert [row["question_id"] for row in livebench.groups["reasoning:spatial"]] == ["q1", "q2"]
    assert livebench.unsupported_rows == {"coding": 1}


def test_aggregate_metrics_counts_rows_and_families() -> None:
    metrics = suite.aggregate_metrics(
        [
            {"rows": 3, "correct": 2, "accepted": 2, "abstained": 1, "failed": 0, "incorrect_attempts": 0},
            {"rows": 2, "correct": 0, "accepted": 1, "abstained": 0, "failed": 1, "incorrect_attempts": 1},
        ]
    )

    assert metrics == {
        "families": 2,
        "rows": 5,
        "correct": 2,
        "accepted": 3,
        "abstained": 1,
        "failed": 1,
        "incorrect_attempts": 1,
        "raw_accuracy": 0.4,
        "coverage": 0.6,
        "attempted_accuracy": 2 / 3,
    }


def test_seal_report_is_canonical_and_rejects_existing_digest() -> None:
    first = suite.seal_report({"b": 2, "a": [1, 3]})
    second = suite.seal_report({"a": [1, 3], "b": 2})

    assert first == second
    assert len(first["report_digest"]) == 64
    with pytest.raises(ValueError, match="already contains"):
        suite.seal_report(first)
