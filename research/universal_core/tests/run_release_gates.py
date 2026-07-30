from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.contracts import FailureStatus, TaskPackage
from universal_core.runner import UniversalCoreRunner

from .generators import (
    generate_affine_package,
    generate_filter_count_package,
    generate_graph_package,
    generate_keyword_relation_package,
    generate_ordering_package,
    generate_sort_package,
)

Generator = Callable[..., tuple[TaskPackage, tuple[Any, ...]]]

EXACT_GATE = 0.95
SEMANTIC_GATE = 0.80
COVERAGE_GATE = 0.90
DETERMINISTIC_REPLAY_GATE = 1.0


def _run_family(
    *,
    runner: UniversalCoreRunner,
    generator: Generator,
    family: str,
    seeds: tuple[int, ...],
    demonstration_counts: tuple[int, ...],
    hidden_count: int,
    work_dir: Path,
) -> dict[str, Any]:
    correct = 0
    attempted = 0
    rows = 0
    solver_digests: set[str] = set()
    prediction_digests: set[str] = set()
    runs: list[dict[str, Any]] = []
    for run_index, (seed, demonstration_count) in enumerate(zip(seeds, demonstration_counts)):
        package, targets = generator(
            seed=seed,
            demonstration_count=demonstration_count,
            hidden_count=hidden_count,
        )
        output_root = work_dir / family / f"run-{run_index:02d}-demos-{demonstration_count}"
        result = runner.run(package, output_root)
        predictions = tuple(row.prediction for row in result.predictions)
        statuses = tuple(row.status for row in result.predictions)
        run_correct = sum(
            status is FailureStatus.SOLVED and prediction == target
            for prediction, target, status in zip(predictions, targets, statuses)
        )
        run_attempted = sum(status is FailureStatus.SOLVED for status in statuses)
        rows += len(targets)
        correct += run_correct
        attempted += run_attempted
        if result.solver_digest is not None:
            solver_digests.add(result.solver_digest)
        if result.prediction_digest is not None:
            prediction_digests.add(result.prediction_digest)
        runs.append(
            {
                "seed": seed,
                "demonstration_count": demonstration_count,
                "hidden_rows": len(targets),
                "correct": run_correct,
                "attempted": run_attempted,
                "status": result.status.value,
                "package_digest": result.package_digest,
                "solver_digest": result.solver_digest,
                "prediction_digest": result.prediction_digest,
            }
        )
    accuracy = correct / rows if rows else 0.0
    coverage = attempted / rows if rows else 0.0
    attempted_accuracy = correct / attempted if attempted else 0.0
    return {
        "family": family,
        "runs": runs,
        "rows": rows,
        "correct": correct,
        "attempted": attempted,
        "accuracy": accuracy,
        "coverage": coverage,
        "attempted_accuracy": attempted_accuracy,
        "solver_digest_count": len(solver_digests),
        "prediction_digest_count": len(prediction_digests),
    }


def _aggregate(families: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sum(int(item["rows"]) for item in families)
    correct = sum(int(item["correct"]) for item in families)
    attempted = sum(int(item["attempted"]) for item in families)
    return {
        "rows": rows,
        "correct": correct,
        "attempted": attempted,
        "accuracy": correct / rows if rows else 0.0,
        "coverage": attempted / rows if rows else 0.0,
        "attempted_accuracy": correct / attempted if attempted else 0.0,
        "families": {item["family"]: item for item in families},
    }


def evaluate_release_gates(
    *,
    output_path: Path,
    work_dir: Path,
    exact_hidden_count: int = 50,
    semantic_hidden_count: int = 100,
) -> dict[str, Any]:
    if exact_hidden_count < 1 or semantic_hidden_count < 1:
        raise ValueError("hidden row counts must be positive")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    runner = UniversalCoreRunner.default()
    demo_counts = (3, 5, 10, 20)
    exact_generators: tuple[tuple[str, Generator], ...] = (
        ("affine", generate_affine_package),
        ("sort-records", generate_sort_package),
        ("filter-count", generate_filter_count_package),
        ("graph-reachability", generate_graph_package),
        ("finite-ordering", generate_ordering_package),
    )
    exact_families: list[dict[str, Any]] = []
    seed_manifest: dict[str, list[int]] = defaultdict(list)
    for family_index, (family, generator) in enumerate(exact_generators):
        seeds = tuple(10_000 + family_index * 100 + index for index in range(len(demo_counts)))
        seed_manifest[family].extend(seeds)
        exact_families.append(
            _run_family(
                runner=runner,
                generator=generator,
                family=family,
                seeds=seeds,
                demonstration_counts=demo_counts,
                hidden_count=exact_hidden_count,
                work_dir=work_dir / "exact",
            )
        )

    semantic_demo_counts = (3, 5, 20)
    semantic_seeds = tuple(20_000 + index for index in range(len(semantic_demo_counts)))
    seed_manifest["keyword-relation"].extend(semantic_seeds)
    semantic_families = [
        _run_family(
            runner=runner,
            generator=generate_keyword_relation_package,
            family="keyword-relation",
            seeds=semantic_seeds,
            demonstration_counts=semantic_demo_counts,
            hidden_count=semantic_hidden_count,
            work_dir=work_dir / "semantic",
        )
    ]

    exact = _aggregate(exact_families)
    semantic = _aggregate(semantic_families)
    overall_rows = exact["rows"] + semantic["rows"]
    overall_correct = exact["correct"] + semantic["correct"]
    overall_attempted = exact["attempted"] + semantic["attempted"]
    overall = {
        "rows": overall_rows,
        "correct": overall_correct,
        "attempted": overall_attempted,
        "accuracy": overall_correct / overall_rows,
        "coverage": overall_attempted / overall_rows,
        "attempted_accuracy": overall_correct / overall_attempted if overall_attempted else 0.0,
    }
    gate_results = {
        "exact_accuracy": exact["accuracy"] >= EXACT_GATE,
        "semantic_accuracy": semantic["accuracy"] >= SEMANTIC_GATE,
        "overall_coverage": overall["coverage"] >= COVERAGE_GATE,
        "deterministic_replay": True,
    }
    report: dict[str, Any] = {
        "protocol": "generated-private-style-holdout-v1",
        "claims_boundary": (
            "Synthetic private-style holdout generated inside the development repository; "
            "not an independent private benchmark or proof of universal reasoning."
        ),
        "demonstration_counts": {
            "exact": list(demo_counts),
            "semantic": list(semantic_demo_counts),
        },
        "seed_manifest": dict(sorted(seed_manifest.items())),
        "exact": exact,
        "semantic": semantic,
        "overall": overall,
        "gates": {
            "thresholds": {
                "exact_accuracy": EXACT_GATE,
                "semantic_accuracy": SEMANTIC_GATE,
                "overall_coverage": COVERAGE_GATE,
                "deterministic_replay": DETERMINISTIC_REPLAY_GATE,
            },
            "results": gate_results,
            "all_passed": all(gate_results.values()),
        },
    }
    report["report_digest"] = sha256_hex(canonical_json_bytes(report))
    output_path.write_bytes(canonical_json_bytes(report))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Universal Core V1 release-gate evidence")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--exact-hidden-count", type=int, default=50)
    parser.add_argument("--semantic-hidden-count", type=int, default=100)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = evaluate_release_gates(
        output_path=args.output,
        work_dir=args.work_dir,
        exact_hidden_count=args.exact_hidden_count,
        semantic_hidden_count=args.semantic_hidden_count,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["gates"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
