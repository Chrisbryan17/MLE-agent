from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .normalizer import normalize_task_payload
from .runner import UniversalCoreRunner


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="universal-core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="infer, freeze, and execute one private task schema")
    run.add_argument("--task", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = json.loads(args.task.read_text(encoding="utf-8"))
        package = normalize_task_payload(payload)
        result = UniversalCoreRunner.default().run(package, args.output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, sort_keys=True), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result.status.value,
                "attempt_id": result.attempt_id,
                "rows": len(result.predictions),
                "solved_rows": sum(row.status.value == "SOLVED" for row in result.predictions),
                "package_digest": result.package_digest,
                "solver_digest": result.solver_digest,
                "prediction_digest": result.prediction_digest,
                "audit_path": result.audit_path,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
