from dataclasses import dataclass
from typing import Any

import pytest

from universal_core.holonomy_v2.grammar_ext import build_task_grammar_extended
from universal_core.holonomy_v2.loops import LoopKind, build_loops
from universal_core.holonomy_v2.program import BudgetExceeded, Program
from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import EngineLimits, SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


RULES = [
    {"left": ["A", "B"], "right": ["C"]},
    {"left": ["C", "C"], "right": []},
]


def test_stack_rewrite_reduces_after_each_push() -> None:
    program = Program.parse({
        "kind": "stack_rewrite",
        "sequence_field": "symbols",
        "token_mode": "items",
        "rules": RULES,
    })

    assert program.run({"symbols": ["A", "B", "A", "B"]}) == []
    assert program.run({"symbols": ["A", "B", "A"]}) == ["C", "A"]


def test_stack_rewrite_preserves_character_strings() -> None:
    program = Program.parse({
        "kind": "stack_rewrite",
        "sequence_field": "text",
        "token_mode": "characters",
        "rules": [
            {"left": ["a", "b"], "right": ["c"]},
            {"left": ["c", "c"], "right": []},
        ],
    })

    assert program.run({"text": "abab"}) == ""


def test_stack_rewrite_rejects_conflicting_rules() -> None:
    with pytest.raises(ValueError, match="conflicting rewrite"):
        Program.parse({
            "kind": "stack_rewrite",
            "sequence_field": "symbols",
            "token_mode": "items",
            "rules": [
                {"left": ["A"], "right": ["B"]},
                {"left": ["A"], "right": ["C"]},
            ],
        })


def test_stack_rewrite_is_bounded() -> None:
    program = Program.parse({
        "kind": "stack_rewrite",
        "sequence_field": "symbols",
        "token_mode": "items",
        "rules": [{"left": ["A"], "right": ["A", "A"]}],
    })

    with pytest.raises(BudgetExceeded, match="step bound"):
        program.run({"symbols": ["A"]}, EngineLimits(max_steps=12))


def test_induces_stack_rewrite_from_explicit_rules() -> None:
    demos = (
        Demo({"symbols": ["A", "B"]}, ["C"]),
        Demo({"symbols": ["A", "B", "A", "B"]}, []),
        Demo({"symbols": ["C", "C", "A"]}, ["A"]),
    )
    instructions = (
        "Read the symbols from left to right using a stack and repeatedly rewrite the top. "
        "Rules: A B -> C; C C -> empty. Return the final stack."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "stack_rewrite"
    assert result.program.run({"symbols": ["A", "B", "A"]}) == ["C", "A"]


def test_stack_rewrite_builds_a_normal_form_loop() -> None:
    demos = (Demo({"symbols": ["A", "B", "A", "B"]}, []),)
    program = Program.parse({
        "kind": "stack_rewrite",
        "sequence_field": "symbols",
        "token_mode": "items",
        "rules": RULES,
    })
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    normal_forms = [item for item in loops.mandatory if item.kind == LoopKind.REWRITE_NORMAL_FORM]
    assert normal_forms
    assert all(item.expected == [] for item in normal_forms)
