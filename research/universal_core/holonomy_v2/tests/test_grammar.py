from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.grammar import build_task_grammar
from universal_core.holonomy_v2.program import Program
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_grammar_grows_order_then_project() -> None:
    demos = (
        Demo(
            [{"glyph": "a", "weight": 3}, {"glyph": "b", "weight": 1}],
            ["b", "a"],
        ),
        Demo(
            [{"glyph": "c", "weight": 0}, {"glyph": "d", "weight": 2}],
            ["c", "d"],
        ),
    )
    grammar = build_task_grammar(
        "Order entries by increasing weight, then return only the glyphs in that order.",
        demos,
        SearchConfig(),
    )
    assert any(
        item.to_data().get("kind") == "compose"
        and [part["kind"] for part in item.to_data()["parts"]] == ["order", "project"]
        for item in grammar.programs
    )


def test_grammar_grows_graph_to_label() -> None:
    demos = (
        Demo({"graph": {"edges": [["a", "b"]]}, "start": "a", "goal": "b"}, "OPEN"),
        Demo({"graph": {"edges": [["a", "b"]]}, "start": "b", "goal": "a"}, "SEALED"),
    )
    grammar = build_task_grammar(
        "Return OPEN when a directed route exists and SEALED otherwise.",
        demos,
        SearchConfig(),
    )
    assert any(item.to_data()["kind"] == "label_map" for item in grammar.programs)


def test_type_invalid_composition_is_rejected() -> None:
    demos = (Demo(3, 7),)
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    assert not grammar.can_compose(
        Program.parse({"kind": "affine", "a": 2, "b": 1}),
        Program.parse({"kind": "project", "field": "x"}),
    )
