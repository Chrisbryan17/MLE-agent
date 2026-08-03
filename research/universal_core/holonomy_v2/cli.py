from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from .blind_adapter import run_public_task_v2
from .engine import HolonomyEngine
from .security import scan_tree
from .types import SearchConfig


def _read(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="universal-core-holonomy-v2")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("induce", "predict", "evidence"):
        item = sub.add_parser(name)
        item.add_argument("--task", required=True)
        item.add_argument("--output", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--root", required=True)
    scan.add_argument("--output", required=True)
    gate = sub.add_parser("regression")
    gate.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "scan":
        report = scan_tree(Path(args.root))
        _write(args.output, report.to_data())
        return 0 if report.ok else 3
    if args.command == "regression":
        command = [
            sys.executable,
            "-m",
            "universal_core.holonomy_v2.tests.run_v2_gates",
            "--output",
            args.output,
        ]
        return subprocess.run(command, check=False).returncode
    task = _read(args.task)
    engine = HolonomyEngine(SearchConfig())
    if args.command == "induce":
        result = engine.induce(str(task["instructions"]), tuple(task["demonstrations"]))
        data = {
            "program": None if result.program is None else result.program.to_data(),
            "abstention": None if result.abstention is None else result.abstention.to_data(),
            "evidence": result.evidence.to_data(),
        }
    else:
        data = run_public_task_v2(task, engine)
        if args.command == "evidence":
            data = {"task_id": data["task_id"], "evidence": data["evidence"], "freeze_digest": data["freeze_digest"]}
    _write(args.output, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
