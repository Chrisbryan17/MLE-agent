from __future__ import annotations

import pytest

from universal_core.minilang import ExecutionLimits, MiniLangProgram


def test_minilang_computes_weighted_sum() -> None:
    program = MiniLangProgram.from_data({
        "kind": "minilang",
        "version": 1,
        "body": [
            {"op": "let", "name": "total", "value": {"literal": 0}},
            {"op": "for_each", "item": "row", "in": {"var": "$input"}, "body": [
                {"op": "set", "name": "total", "value": {
                    "call": "add",
                    "args": [{"var": "total"}, {"call": "multiply", "args": [
                        {"index": [{"var": "row"}, 0]}, {"index": [{"var": "row"}, 1]}
                    ]}],
                }},
            ]},
            {"op": "return", "value": {"var": "total"}},
        ],
    })
    assert program.run([[2, 3], [4, 5]], ExecutionLimits()) == 26
    assert program.to_data()["kind"] == "minilang"
    assert len(program.digest) == 64


def test_minilang_supports_conditional_classification() -> None:
    program = MiniLangProgram.from_data({
        "kind": "minilang",
        "version": 1,
        "body": [{
            "op": "if",
            "condition": {"call": "contains", "args": [{"call": "lower", "args": [{"var": "$input"}]}, {"literal": "urgent"}]},
            "then": [{"op": "return", "value": {"literal": "alert"}}],
            "else": [{"op": "return", "value": {"literal": "normal"}}],
        }],
    })
    assert program.run("URGENT failure") == "alert"
    assert program.run("routine update") == "normal"


def test_minilang_requires_return() -> None:
    program = MiniLangProgram.from_data({
        "kind": "minilang", "version": 1,
        "body": [{"op": "let", "name": "x", "value": {"literal": 1}}],
    })
    with pytest.raises(RuntimeError, match="did not return"):
        program.run(0)
