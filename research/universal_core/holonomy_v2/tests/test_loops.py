from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.grammar import build_task_grammar
from universal_core.holonomy_v2.loops import LoopKind, build_loops
from universal_core.holonomy_v2.program import Program
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def _fixture():
    demos = (
        Demo([{"glyph": "a", "weight": 3}, {"glyph": "b", "weight": 1}], ["b", "a"]),
        Demo([{"glyph": "c", "weight": 0}, {"glyph": "d", "weight": 2}], ["c", "d"]),
    )
    program = Program.parse({
        "kind": "compose",
        "parts": [
            {"kind": "order", "field": "weight", "descending": False},
            {"kind": "project", "field": "glyph"},
        ],
    })
    grammar = build_task_grammar("Order by weight and return glyph.", demos, SearchConfig())
    return demos, program, grammar


def test_builds_replay_and_key_rename_loops() -> None:
    demos, program, grammar = _fixture()
    loops = build_loops(program, demos, grammar)
    kinds = {item.kind for item in loops.mandatory}
    assert LoopKind.DEMONSTRATION_REPLAY in kinds
    assert LoopKind.KEY_RENAME_ROUND_TRIP in kinds


def test_compose_program_adds_path_agreement_loop() -> None:
    demos, program, grammar = _fixture()
    loops = build_loops(program, demos, grammar)
    assert any(item.kind is LoopKind.PATH_AGREEMENT for item in loops.mandatory)


def test_key_rename_loop_uses_changed_fields() -> None:
    demos, program, grammar = _fixture()
    loops = build_loops(program, demos, grammar)
    item = next(loop for loop in loops.mandatory if loop.kind is LoopKind.KEY_RENAME_ROUND_TRIP)
    assert "weight" not in repr(item.input_value)
    assert "glyph" not in repr(item.input_value)
