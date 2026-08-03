from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.grammar import build_task_grammar
from universal_core.holonomy_v2.loops import build_loops
from universal_core.holonomy_v2.program import Program
from universal_core.holonomy_v2.residuals import check_residuals, value_distance
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_zero_residual_accepts_candidate() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    program = Program.parse({"kind": "affine", "a": 2, "b": 1})
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    report = check_residuals(program, build_loops(program, demos, grammar))
    assert report.mandatory_pass
    assert report.mandatory_total >= 3
    assert report.digest


def test_nonzero_mandatory_residual_rejects_candidate() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    bad = Program.parse({"kind": "affine", "a": 2, "b": 0})
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    report = check_residuals(bad, build_loops(bad, demos, grammar))
    assert not report.mandatory_pass
    assert any(item.distance > 0 for item in report.entries)


def test_structural_distance_counts_nested_mismatch() -> None:
    assert value_distance({"a": [1, 2]}, {"a": [1, 3]}) == 1
    assert value_distance([1, 2], [1, 2]) == 0
