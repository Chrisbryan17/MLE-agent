from __future__ import annotations

import pytest

from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.contracts import (
    Demonstration,
    FailureStatus,
    OutputSchema,
    TaskPackage,
)


def test_task_package_accepts_three_to_twenty_demonstrations() -> None:
    demos = tuple(Demonstration(input=i, output=i + 1) for i in range(3))
    package = TaskPackage(
        "add one",
        demos,
        (20,),
        OutputSchema(kind="integer"),
        {"task_name": "ignored"},
    )
    assert len(package.package_digest) == 64


def test_task_package_rejects_too_few_or_too_many_demonstrations() -> None:
    with pytest.raises(ValueError, match="3 to 20"):
        TaskPackage(
            "identity",
            (Demonstration(input=1, output=1),),
            (4,),
            OutputSchema(kind="integer"),
            {},
        )
    with pytest.raises(ValueError, match="3 to 20"):
        TaskPackage(
            "identity",
            tuple(Demonstration(input=i, output=i) for i in range(21)),
            (4,),
            OutputSchema(kind="integer"),
            {},
        )


def test_task_package_rejects_hidden_targets_recursively() -> None:
    demos = tuple(Demonstration(input=i, output=i) for i in range(3))
    with pytest.raises(ValueError, match="hidden target"):
        TaskPackage(
            "identity",
            demos,
            ({"input": 1, "nested": {"target": 1}},),
            OutputSchema(kind="integer"),
            {},
        )


def test_inert_metadata_does_not_change_digest() -> None:
    demos = tuple(Demonstration(input=i, output=i) for i in range(3))
    a = TaskPackage(
        "identity", demos, (4,), OutputSchema(kind="integer"), {"task_name": "alpha"}
    )
    b = TaskPackage(
        "identity", demos, (4,), OutputSchema(kind="integer"), {"task_name": "beta"}
    )
    assert a.package_digest == b.package_digest


def test_canonical_bytes_are_stable_and_terminated() -> None:
    raw = canonical_json_bytes({"b": 2, "a": 1})
    assert raw == b'{"a":1,"b":2}\n'
    assert sha256_hex(raw) == sha256_hex(raw)


def test_failure_status_values_are_stable() -> None:
    assert [status.value for status in FailureStatus] == [
        "SOLVED",
        "AMBIGUOUS_TASK",
        "INSUFFICIENT_DEMONSTRATIONS",
        "UNSUPPORTED_OPERATION",
        "VERIFICATION_FAILED",
        "EXECUTION_FAILED",
        "OUTPUT_SCHEMA_CONFLICT",
        "LOW_CONFIDENCE",
    ]
