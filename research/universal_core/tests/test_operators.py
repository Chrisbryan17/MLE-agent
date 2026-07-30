from __future__ import annotations

import pytest

from universal_core.operators import default_registry
from universal_core.programs import OperatorProgram, OperatorStep


def test_operator_program_sorts_records_by_field() -> None:
    program = OperatorProgram((
        OperatorStep("sort_records", "$input", "sorted", {"field": 1, "descending": False}),
        OperatorStep("return_value", "sorted", "$output", {}),
    ))
    assert program.run([["a", 3], ["b", 1]], default_registry()) == [["b", 1], ["a", 3]]


def test_operator_program_can_filter_then_count() -> None:
    program = OperatorProgram((
        OperatorStep("filter_compare", "$input", "eligible", {"field": 1, "comparison": ">=", "value": 10}),
        OperatorStep("count", "eligible", "total", {}),
        OperatorStep("return_value", "total", "$output", {}),
    ))
    assert program.run([["a", 9], ["b", 10], ["c", 12]]) == 2


def test_registry_rejects_unknown_operator() -> None:
    with pytest.raises(KeyError, match="unknown operator"):
        default_registry().execute("benchmark_specific_route", 1, {})


def test_graph_operators_are_deterministic() -> None:
    registry = default_registry()
    graph = {"edges": [["a", "b"], ["b", "c"], ["a", "d"]], "directed": True}
    assert registry.execute("graph_reachable", graph, {"start": "a", "goal": "c"}) is True
    assert registry.execute("shortest_path_length", graph, {"start": "a", "goal": "c"}) == 2
    assert registry.execute("shortest_path_length", graph, {"start": "c", "goal": "a"}) is None


def test_operator_program_serialization_has_stable_digest() -> None:
    program = OperatorProgram((OperatorStep("count", "$input", "$output", {}),))
    assert len(program.digest) == 64
    assert program.to_data()["steps"][0]["operator"] == "count"
