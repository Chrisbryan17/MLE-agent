from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.connection import ConnectionGraph
from universal_core.holonomy_v2.grammar import build_task_grammar
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_connection_graph_records_provenance() -> None:
    demos = (
        Demo(1, 3),
        Demo(2, 5),
        Demo(3, 7),
    )
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    graph = ConnectionGraph.from_demonstrations(demos, grammar)
    assert graph.vertices
    assert graph.edges
    assert any(edge.provenance == (0, 1, 2) for edge in graph.edges)


def test_path_order_is_deterministic() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    grammar = build_task_grammar("Return 2*n+1.", demos, SearchConfig())
    graph = ConnectionGraph.from_demonstrations(demos, grammar)
    first = graph.find_path(grammar.source_schema, grammar.target_schema, max_edges=2)
    second = graph.find_path(grammar.source_schema, grammar.target_schema, max_edges=2)
    assert [tuple(edge.program.digest for edge in path) for path in first] == [
        tuple(edge.program.digest for edge in path) for path in second
    ]
    assert graph.compose(first[0]).run(4) == 9
