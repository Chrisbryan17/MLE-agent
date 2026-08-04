from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import suite
from .adapters import execution


FROZEN_CORE_COMMIT = "1d7c489bcdbff755d638b35ad47ce62bd4fe829d"
SNAPSHOT_INVENTORY_DIGEST = "486badc9ccc8eb4911b1b7f234d785c68c4ff3e53f5d320d7c230e1ceff3dff3"
CORE_PATH = "research/universal_core/holonomy_v2"


def verify_frozen_core(repo_root: Path | str) -> None:
    root = Path(repo_root)
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{FROZEN_CORE_COMMIT}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if exists.returncode != 0:
        raise RuntimeError("frozen core commit is unavailable in the checkout")
    diff = subprocess.run(
        ["git", "diff", "--quiet", FROZEN_CORE_COMMIT, "--", CORE_PATH],
        cwd=root,
        check=False,
    )
    if diff.returncode != 0:
        raise RuntimeError("frozen core path differs from the recorded commit")


def _read_manifest(vendor: Path) -> Mapping[str, Any]:
    path = vendor / suite.MANIFEST_NAME
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("snapshot manifest must be a mapping")
    if value.get("inventory_digest") != SNAPSHOT_INVENTORY_DIGEST:
        raise ValueError("snapshot inventory digest does not match the pinned corpus")
    return value


def _failed_metrics(task_id: str, rows: int) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "rows": rows,
        "correct": 0,
        "accepted": 0,
        "abstained": 0,
        "failed": rows,
        "incorrect_attempts": 0,
        "raw_accuracy": 0.0,
        "coverage": 0.0,
        "attempted_accuracy": 0.0,
    }


def _failed_raw(task_id: str, rows: int) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "program_digest": None,
        "freeze_digest": None,
        "prediction_digest": None,
        "predictions": [
            {"status": "RUNNER_FAILED", "prediction": None}
            for _ in range(rows)
        ],
    }


def _arc_failure(task_id: str, payload: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
    raw_test = payload.get("test")
    rows = len(raw_test) if isinstance(raw_test, (list, tuple)) else 0
    raw = _failed_raw(task_id, rows)
    fallback = [{"attempt_1": [[0]], "attempt_2": [[0]]} for _ in range(rows)]
    return {
        "benchmark": "arc_agi_2",
        "task_id": task_id,
        "raw_result": raw,
        "submission": fallback,
        "metrics": _failed_metrics(task_id, rows),
        "error_type": type(exc).__name__,
    }


def _bbeh_failure(
    task_id: str,
    payload: Mapping[str, Any],
    demonstration_count: int,
    exc: Exception,
) -> dict[str, Any]:
    examples = payload.get("examples")
    total = len(examples) if isinstance(examples, (list, tuple)) else 0
    rows = max(0, total - demonstration_count)
    return {
        "benchmark": "bbeh_transfer",
        "task_id": task_id,
        "demonstration_count": demonstration_count,
        "raw_result": _failed_raw(task_id, rows),
        "metrics": _failed_metrics(task_id, rows),
        "error_type": type(exc).__name__,
    }


def _livebench_failure(
    key: str,
    rows_data: Sequence[Mapping[str, Any]],
    demonstration_count: int,
    exc: Exception,
) -> dict[str, Any]:
    category, family = key.split(":", 1)
    task_id = f"livebench:{category}:{family}"
    rows = max(0, len(rows_data) - demonstration_count)
    metrics = _failed_metrics(task_id, rows)
    metrics.update({"category": category, "family": family})
    return {
        "benchmark": "livebench_scalar_transfer",
        "task_id": task_id,
        "category": category,
        "family": family,
        "demonstration_count": demonstration_count,
        "raw_result": _failed_raw(task_id, rows),
        "metrics": metrics,
        "error_type": type(exc).__name__,
    }


def _effective_demonstrations(requested: int, row_count: int) -> int:
    if type(requested) is not int or requested <= 0:
        raise ValueError("demonstration count must be a positive integer")
    if row_count < 2:
        raise ValueError("benchmark family requires at least two rows")
    return min(requested, row_count - 1)


def run_public_benchmarks(
    vendor: Path | str,
    engine: Any,
    *,
    mode: str,
    run_label: str,
    bbeh_demonstrations: int = 5,
    livebench_demonstrations: int = 5,
    adapter_commit: str | None = None,
) -> dict[str, Any]:
    if mode not in {"smoke", "full"}:
        raise ValueError("benchmark mode must be smoke or full")
    if not isinstance(run_label, str) or not run_label:
        raise ValueError("run label must be a non-empty string")
    vendor_path = Path(vendor)
    _read_manifest(vendor_path)

    arc_tasks = suite.load_arc_tasks(vendor_path, "evaluation")
    bbeh_tasks = suite.load_bbeh_tasks(vendor_path)
    livebench = suite.load_livebench(vendor_path)
    if mode == "smoke":
        arc_tasks = arc_tasks[:1]
        bbeh_tasks = bbeh_tasks[:1]
        live_groups = tuple(livebench.groups.items())[:1]
    else:
        live_groups = tuple(livebench.groups.items())

    arc_reports: list[dict[str, Any]] = []
    arc_submission: dict[str, Any] = {}
    for task_id, payload in arc_tasks:
        try:
            report = execution.run_arc_payload(task_id, payload, engine)
        except Exception as exc:
            report = _arc_failure(task_id, payload, exc)
        arc_reports.append(report)
        arc_submission[task_id] = report["submission"]

    bbeh_reports: list[dict[str, Any]] = []
    for task_id, payload in bbeh_tasks:
        raw_examples = payload.get("examples")
        row_count = len(raw_examples) if isinstance(raw_examples, (list, tuple)) else 0
        demos = _effective_demonstrations(bbeh_demonstrations, row_count)
        try:
            report = execution.run_bbeh_payload(
                task_id,
                payload,
                engine,
                demonstration_count=demos,
            )
        except Exception as exc:
            report = _bbeh_failure(task_id, payload, demos, exc)
        bbeh_reports.append(report)

    live_reports: list[dict[str, Any]] = []
    for key, rows_data in live_groups:
        demos = _effective_demonstrations(livebench_demonstrations, len(rows_data))
        try:
            report = execution.run_livebench_rows(
                rows_data,
                engine,
                demonstration_count=demos,
            )
        except Exception as exc:
            report = _livebench_failure(key, rows_data, demos, exc)
        live_reports.append(report)

    report = {
        "schema_version": 1,
        "run_label": run_label,
        "mode": mode,
        "identity": {
            "frozen_core_commit": FROZEN_CORE_COMMIT,
            "adapter_commit": adapter_commit,
            "snapshot_inventory_digest": SNAPSHOT_INVENTORY_DIGEST,
        },
        "settings": {
            "arc_split": "evaluation",
            "bbeh_demonstrations_requested": bbeh_demonstrations,
            "livebench_demonstrations_requested": livebench_demonstrations,
        },
        "arc_agi_2": {
            "evaluated_tasks": len(arc_reports),
            "metrics": suite.aggregate_metrics(item["metrics"] for item in arc_reports),
            "reports": arc_reports,
            "submission": arc_submission,
        },
        "bbeh_transfer": {
            "evaluated_families": len(bbeh_reports),
            "metrics": suite.aggregate_metrics(item["metrics"] for item in bbeh_reports),
            "reports": bbeh_reports,
        },
        "livebench_scalar_transfer": {
            "evaluated_families": len(live_reports),
            "metrics": suite.aggregate_metrics(item["metrics"] for item in live_reports),
            "unsupported_rows": dict(livebench.unsupported_rows),
            "reports": live_reports,
        },
    }
    return suite.seal_report(report)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_outputs(report: Mapping[str, Any], output: Path | str) -> dict[str, str]:
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "report.json"
    submission_path = root / "arc_submission.json"
    checksums_path = root / "SHA256SUMS.txt"
    _write_json(report_path, report)
    arc = report.get("arc_agi_2")
    if not isinstance(arc, Mapping) or not isinstance(arc.get("submission"), Mapping):
        raise ValueError("report lacks ARC submission mapping")
    _write_json(submission_path, arc["submission"])
    checksums_path.write_text(
        "".join(
            f"{_file_digest(path)}  {path.name}\n"
            for path in (submission_path, report_path)
        ),
        encoding="utf-8",
    )
    return {
        "report": str(report_path),
        "arc_submission": str(submission_path),
        "checksums": str(checksums_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pinned public benchmarks against frozen V2")
    parser.add_argument("--vendor-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--adapter-commit")
    parser.add_argument("--bbeh-demonstrations", type=int, default=5)
    parser.add_argument("--livebench-demonstrations", type=int, default=5)
    args = parser.parse_args(argv)

    verify_frozen_core(args.repo_root)
    root = Path(args.vendor_root)
    vendor = root if (root / suite.MANIFEST_NAME).is_file() else suite.locate_vendor(root)

    from research.universal_core.holonomy_v2.engine import HolonomyEngine
    from research.universal_core.holonomy_v2.types import SearchConfig

    engine = HolonomyEngine(SearchConfig())
    report = run_public_benchmarks(
        vendor,
        engine,
        mode=args.mode,
        run_label=args.run_label,
        bbeh_demonstrations=args.bbeh_demonstrations,
        livebench_demonstrations=args.livebench_demonstrations,
        adapter_commit=args.adapter_commit,
    )
    write_outputs(report, args.output)
    print(
        json.dumps(
            {
                "report_digest": report["report_digest"],
                "arc": report["arc_agi_2"]["metrics"],
                "bbeh": report["bbeh_transfer"]["metrics"],
                "livebench": report["livebench_scalar_transfer"]["metrics"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
