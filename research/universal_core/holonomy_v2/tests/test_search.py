from dataclasses import dataclass, replace
from typing import Any

from universal_core.holonomy_v2.grammar import build_task_grammar
from universal_core.holonomy_v2.program import Program
from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import EngineLimits, FailureCode, SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_finds_order_then_project() -> None:
    demos = (
        Demo([{"glyph": "a", "weight": 3}, {"glyph": "b", "weight": 1}], ["b", "a"]),
        Demo([{"glyph": "c", "weight": 0}, {"glyph": "d", "weight": 2}], ["c", "d"]),
    )
    result = search_candidates(
        "Order by weight ascending, then return only glyph.",
        demos,
        SearchConfig(),
    )
    assert result.program is not None
    assert result.program.run([{"glyph": "x", "weight": 5}, {"glyph": "y", "weight": -1}]) == ["y", "x"]
    assert result.report is not None and result.report.mandatory_pass


def test_finds_graph_to_label() -> None:
    demos = (
        Demo({"graph": {"edges": [["a", "b"]]}, "start": "a", "goal": "b"}, "OPEN"),
        Demo({"graph": {"edges": [["a", "b"]]}, "start": "b", "goal": "a"}, "SEALED"),
    )
    result = search_candidates(
        "Return OPEN when a directed route exists and SEALED otherwise.",
        demos,
        SearchConfig(),
    )
    assert result.program is not None
    assert result.program.run({"graph": {"edges": []}, "start": "a", "goal": "z"}) == "SEALED"


def test_prunes_candidate_that_fails_mandatory_replay() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    bad = Program.parse({"kind": "affine", "a": 2, "b": 0})
    grammar = replace(grammar, programs=(bad,) + grammar.programs)
    result = search_candidates("Return 2*n+1.", demos, SearchConfig(), grammar=grammar)
    assert result.program is not None
    assert result.program.run(4) == 9
    assert result.stats.pruned_loop >= 1


def test_reports_budget_exhaustion() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    config = SearchConfig(limits=EngineLimits(max_candidates=1))
    result = search_candidates("Return 2*n+1.", demos, config)
    assert result.program is None
    assert result.abstention is not None
    assert result.abstention.code is FailureCode.SEARCH_BUDGET_EXCEEDED


def test_marks_indistinguishable_equal_rank_candidates_ambiguous() -> None:
    demos = (Demo(0, 0),)
    grammar = build_task_grammar("Return the input.", demos, SearchConfig())
    identity = Program.parse({"kind": "input"})
    affine = Program.parse({"kind": "affine", "a": 1, "b": 0})
    grammar = replace(grammar, programs=(identity, affine))
    result = search_candidates("Return the input.", demos, SearchConfig(), grammar=grammar)
    assert result.program is None
    assert result.abstention is not None
    assert result.abstention.code is FailureCode.AMBIGUOUS_PROGRAM
