from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


MANIFEST_NAME = "SNAPSHOT_MANIFEST.json"


@dataclass(frozen=True)
class LiveBenchCorpus:
    groups: Mapping[str, tuple[Mapping[str, Any], ...]]
    unsupported_rows: Mapping[str, int]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def locate_vendor(root: Path | str) -> Path:
    base = Path(root)
    manifests = sorted(path for path in base.rglob(MANIFEST_NAME) if path.is_file())
    if len(manifests) != 1:
        raise ValueError(f"expected exactly one {MANIFEST_NAME}, found {len(manifests)}")
    return manifests[0].parent


def load_arc_tasks(vendor: Path | str, split: str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    if split not in {"training", "evaluation"}:
        raise ValueError("ARC split must be training or evaluation")
    directory = Path(vendor) / "arc_agi_2" / "data" / split
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError(f"ARC split is empty: {split}")
    tasks: list[tuple[str, Mapping[str, Any]]] = []
    for path in paths:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            raise ValueError(f"ARC task must be a mapping: {path}")
        tasks.append((path.stem, payload))
    return tuple(tasks)


def load_bbeh_tasks(vendor: Path | str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    root = Path(vendor) / "bbeh" / "full"
    paths = sorted(root.glob("*/task.json"), key=lambda path: path.parent.name)
    if not paths:
        raise ValueError("BBEH full task set is empty")
    tasks: list[tuple[str, Mapping[str, Any]]] = []
    for path in paths:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            raise ValueError(f"BBEH task must be a mapping: {path}")
        tasks.append((path.parent.name, payload))
    return tuple(tasks)


def load_livebench(vendor: Path | str) -> LiveBenchCorpus:
    root = Path(vendor) / "livebench" / "questions"
    paths = sorted(root.glob("*.jsonl"))
    if not paths:
        raise ValueError("LiveBench question set is empty")

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    unsupported: dict[str, int] = {}
    seen_ids: set[str] = set()
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise ValueError(f"LiveBench row must be a mapping: {path}:{line_number}")
            question_id = row.get("question_id")
            category = row.get("category")
            family = row.get("task")
            if not isinstance(question_id, str) or not question_id:
                raise ValueError(f"LiveBench row lacks question id: {path}:{line_number}")
            if question_id in seen_ids:
                raise ValueError(f"duplicate LiveBench question id: {question_id}")
            seen_ids.add(question_id)
            if not isinstance(category, str) or not category or not isinstance(family, str) or not family:
                raise ValueError(f"LiveBench row lacks category or task: {path}:{line_number}")
            target = row.get("ground_truth")
            if not isinstance(target, str) or not target:
                unsupported[category] = unsupported.get(category, 0) + 1
                continue
            key = f"{category}:{family}"
            grouped.setdefault(key, []).append(row)

    ordered_groups = {
        key: tuple(sorted(rows, key=lambda row: str(row["question_id"])))
        for key, rows in sorted(grouped.items())
    }
    return LiveBenchCorpus(
        groups=ordered_groups,
        unsupported_rows=dict(sorted(unsupported.items())),
    )


def aggregate_metrics(metrics: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = tuple(metrics)
    totals = {
        "rows": 0,
        "correct": 0,
        "accepted": 0,
        "abstained": 0,
        "failed": 0,
        "incorrect_attempts": 0,
    }
    for item in items:
        for key in totals:
            value = item.get(key)
            if type(value) is not int or value < 0:
                raise ValueError(f"metric {key} must be a non-negative integer")
            totals[key] += value
    rows = totals["rows"]
    accepted = totals["accepted"]
    return {
        "families": len(items),
        **totals,
        "raw_accuracy": totals["correct"] / rows if rows else 0.0,
        "coverage": accepted / rows if rows else 0.0,
        "attempted_accuracy": totals["correct"] / accepted if accepted else 0.0,
    }


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def seal_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if "report_digest" in report:
        raise ValueError("report already contains a digest")
    body = dict(report)
    digest = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return {**body, "report_digest": digest}
