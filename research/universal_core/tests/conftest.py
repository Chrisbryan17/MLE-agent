from __future__ import annotations

import pytest

from universal_core.contracts import Demonstration, OutputSchema, TaskPackage


@pytest.fixture
def task_package() -> TaskPackage:
    return TaskPackage(
        instructions="Return records sorted by their numeric score in ascending order.",
        demonstrations=(
            Demonstration([["a", 2], ["b", 1]], [["b", 1], ["a", 2]]),
            Demonstration([["c", 4], ["d", 3]], [["d", 3], ["c", 4]]),
            Demonstration([["e", 9], ["f", 5]], [["f", 5], ["e", 9]]),
        ),
        hidden_inputs=([["x", 7], ["y", 5]],),
        output_schema=OutputSchema(kind="list"),
        metadata={"task_name": "randomized-name", "row_id": "inert"},
    )


@pytest.fixture
def affine_package() -> TaskPackage:
    return TaskPackage(
        instructions="Apply the same arithmetic transformation to each number.",
        demonstrations=(
            Demonstration(1, 5),
            Demonstration(2, 8),
            Demonstration(4, 14),
            Demonstration(-1, -1),
            Demonstration(10, 32),
        ),
        hidden_inputs=(3, 8),
        output_schema=OutputSchema(kind="integer"),
        metadata={"task_name": "private-affine"},
    )
