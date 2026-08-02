from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping, Sequence

from .loops import LoopKind, LoopSet
from .program import Program


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=repr) + "\n").encode()


def value_distance(left: Any, right: Any) -> int | float:
    if left == right:
        return 0
    if isinstance(left, Real) and not isinstance(left, bool) and isinstance(right, Real) and not isinstance(right, bool):
        return abs(float(left) - float(right))
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        left_keys = set(left)
        right_keys = set(right)
        total: int | float = len(left_keys ^ right_keys)
        for key in left_keys & right_keys:
            total += value_distance(left[key], right[key])
        return total
    if (
        isinstance(left, Sequence)
        and not isinstance(left, (str, bytes, bytearray))
        and isinstance(right, Sequence)
        and not isinstance(right, (str, bytes, bytearray))
    ):
        total = abs(len(left) - len(right))
        for a, b in zip(left, right):
            total += value_distance(a, b)
        return total
    if isinstance(left, set) and isinstance(right, set):
        return len(left ^ right)
    return 1


@dataclass(frozen=True)
class ResidualEntry:
    kind: LoopKind
    mandatory: bool
    index: int
    distance: int | float
    actual: Any
    expected: Any
    note: str

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "mandatory": self.mandatory,
            "index": self.index,
            "distance": self.distance,
            "actual": self.actual,
            "expected": self.expected,
            "note": self.note,
        }


@dataclass(frozen=True)
class ResidualReport:
    entries: tuple[ResidualEntry, ...]
    mandatory_pass: bool
    mandatory_total: int
    mandatory_failed: int
    optional_score: float
    digest: str

    def to_data(self) -> dict[str, Any]:
        return {
            "entries": [item.to_data() for item in self.entries],
            "mandatory_pass": self.mandatory_pass,
            "mandatory_total": self.mandatory_total,
            "mandatory_failed": self.mandatory_failed,
            "optional_score": self.optional_score,
            "digest": self.digest,
        }


def check_residuals(program: Program, loops: LoopSet) -> ResidualReport:
    del program
    entries: list[ResidualEntry] = []
    for index, loop in enumerate(loops.all):
        try:
            actual = Program.parse(loop.program_data).run(loop.input_value)
            distance = value_distance(actual, loop.expected)
        except Exception as exc:
            actual = {"error": type(exc).__name__, "message": str(exc)}
            distance = 1
        entries.append(ResidualEntry(
            kind=loop.kind,
            mandatory=loop.mandatory,
            index=index,
            distance=distance,
            actual=actual,
            expected=loop.expected,
            note=loop.note,
        ))
    mandatory = [item for item in entries if item.mandatory]
    optional = [item for item in entries if not item.mandatory]
    failed = sum(item.distance != 0 for item in mandatory)
    optional_score = 0.0 if not optional else sum(item.distance == 0 for item in optional) / len(optional)
    payload = {
        "entries": [item.to_data() for item in entries],
        "mandatory_pass": failed == 0,
        "mandatory_total": len(mandatory),
        "mandatory_failed": failed,
        "optional_score": optional_score,
    }
    digest = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return ResidualReport(
        entries=tuple(entries),
        mandatory_pass=failed == 0,
        mandatory_total=len(mandatory),
        mandatory_failed=failed,
        optional_score=optional_score,
        digest=digest,
    )
