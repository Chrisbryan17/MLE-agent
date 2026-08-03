from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from universal_core.holonomy_v2.blind_adapter import run_public_task_v2
from universal_core.holonomy_v2.engine import HolonomyEngine
from universal_core.holonomy_v2.security import scan_tree
from universal_core.holonomy_v2.tests.regression.run001.family_generator import generate_mutation
from universal_core.holonomy_v2.types import SearchConfig


def _bytes(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(data))


def _measure(seeds: Iterable[int]) -> dict[str, Any]:
    rows = attempted = correct = failures = 0
    task_data: list[dict[str, Any]] = []
    for seed in seeds:
        task = generate_mutation(seed)
        output = run_public_task_v2(task, HolonomyEngine(SearchConfig()))
        task_rows = task_attempted = task_correct = task_failures = 0
        for prediction, target in zip(output["predictions"], task["targets"]):
            rows += 1
            task_rows += 1
            if prediction["status"] == "ACCEPTED":
                attempted += 1
                task_attempted += 1
                hit = prediction["prediction"] == target
                correct += int(hit)
                task_correct += int(hit)
            elif prediction["status"] == "EXECUTION_FAILED":
                failures += 1
                task_failures += 1
        task_data.append({
            "seed": seed,
            "rows": task_rows,
            "attempted": task_attempted,
            "correct": task_correct,
            "failures": task_failures,
            "program_digest": output["program_digest"],
            "freeze_digest": output["freeze_digest"],
            "prediction_digest": output["prediction_digest"],
        })
    return {
        "rows": rows,
        "attempted": attempted,
        "correct": correct,
        "failures": failures,
        "coverage": attempted / rows if rows else 0.0,
        "raw_accuracy": correct / rows if rows else 0.0,
        "attempted_accuracy": correct / attempted if attempted else 0.0,
        "tasks": task_data,
    }


def _replay(seeds: Sequence[int]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    match = True
    for seed in seeds:
        task = generate_mutation(seed)
        left = run_public_task_v2(task, HolonomyEngine(SearchConfig()))
        right = run_public_task_v2(task, HolonomyEngine(SearchConfig()))
        same = _bytes(left) == _bytes(right)
        match = match and same
        pairs.append({
            "seed": seed,
            "match": same,
            "program_digest": left["program_digest"],
            "freeze_digest": left["freeze_digest"],
            "prediction_digest": left["prediction_digest"],
        })
    return {"match": match, "pairs": pairs}


def _manifest(root: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "SHA256.json":
            continue
        data[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return data


def run_gates(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    family_seeds = tuple(family + 12 * (100 + repeat) for family in range(12) for repeat in range(5))
    family = _measure(family_seeds)
    mutation = _measure(range(40))
    replay = _replay((0, 6, 8, 9, 10, 11))
    root = Path(__file__).parents[1]
    security = scan_tree(root).to_data()

    family_ok = family["rows"] == 600 and family["attempted"] == 600 and family["correct"] == 600
    mutation_ok = mutation["rows"] == 400 and mutation["coverage"] >= 0.95 and mutation["raw_accuracy"] >= 0.95
    summary = {
        "ok": bool(family_ok and mutation_ok and replay["match"] and security["ok"]),
        "family": {key: value for key, value in family.items() if key != "tasks"},
        "mutation": {key: value for key, value in mutation.items() if key != "tasks"},
        "replay": replay,
        "security": security,
    }

    _write(output / "family-regression.json", family)
    _write(output / "mutation-regression.json", mutation)
    _write(output / "replay.json", replay)
    _write(output / "security.json", security)
    _write(output / "summary.json", summary)
    _write(output / "SHA256.json", _manifest(output))
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="holonomy-v2-gates")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = run_gates(Path(args.output))
    print(_bytes(summary).decode("utf-8"), end="")
    return 0 if summary["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
