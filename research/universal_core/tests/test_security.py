from __future__ import annotations

from pathlib import Path

import pytest

from universal_core.minilang import (
    ExecutionLimits,
    MiniLangProgram,
    MiniLangValidationError,
)


def test_minilang_rejects_host_access() -> None:
    with pytest.raises(MiniLangValidationError):
        MiniLangProgram.from_data({"kind": "minilang", "version": 1, "body": [{"op": "import", "name": "os"}]})


def test_minilang_rejects_unknown_function() -> None:
    with pytest.raises(MiniLangValidationError, match="function"):
        MiniLangProgram.from_data({
            "kind": "minilang", "version": 1,
            "body": [{"op": "return", "value": {"call": "open_file", "args": [{"literal": "/etc/passwd"}]}}],
        })


def test_minilang_enforces_step_budget() -> None:
    program = MiniLangProgram.from_data({
        "kind": "minilang", "version": 1,
        "body": [
            {"op": "for_each", "item": "x", "in": {"var": "$input"}, "body": []},
            {"op": "return", "value": {"literal": 0}},
        ],
    })
    with pytest.raises(RuntimeError, match="step budget"):
        program.run(list(range(100)), ExecutionLimits(max_steps=10))


def test_minilang_enforces_loop_and_output_limits() -> None:
    loop_program = MiniLangProgram.from_data({
        "kind": "minilang", "version": 1,
        "body": [{"op": "for_each", "item": "x", "in": {"var": "$input"}, "body": []},
                 {"op": "return", "value": {"literal": 0}}],
    })
    with pytest.raises(RuntimeError, match="loop item"):
        loop_program.run(list(range(5)), ExecutionLimits(max_loop_items=4))

    output_program = MiniLangProgram.from_data({
        "kind": "minilang", "version": 1,
        "body": [{"op": "return", "value": {"var": "$input"}}],
    })
    with pytest.raises(RuntimeError, match="output size"):
        output_program.run("x" * 100, ExecutionLimits(max_output_bytes=10))


def test_production_minilang_contains_no_dynamic_python_execution() -> None:
    source = (Path(__file__).parents[1] / "minilang.py").read_text()
    forbidden = ("eval" + "(", "exec" + "(", "__import__", "subprocess", "socket")
    assert not any(token in source for token in forbidden)
