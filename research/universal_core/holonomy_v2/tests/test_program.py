import pytest

from universal_core.holonomy_v2.program import BudgetExceeded, Program
from universal_core.holonomy_v2.types import EngineLimits


def test_order_then_project() -> None:
    program = Program.parse({
        "kind": "compose",
        "parts": [
            {"kind": "order", "field": "score", "descending": True},
            {"kind": "project", "field": "id"},
        ],
    })
    value = [{"id": "a", "score": 1}, {"id": "b", "score": 4}]
    assert program.run(value) == ["b", "a"]


def test_filter_then_aggregate() -> None:
    program = Program.parse({
        "kind": "compose",
        "parts": [
            {"kind": "filter", "field": "charge", "comparison": ">=", "value": 10},
            {"kind": "aggregate", "op": "sum", "field": "payload"},
        ],
    })
    value = [{"charge": 9, "payload": 100}, {"charge": 10, "payload": 4}]
    assert program.run(value) == 4


def test_graph_to_label() -> None:
    program = Program.parse({
        "kind": "label_map",
        "source": {"kind": "graph_reachable"},
        "mapping": {"true": "OPEN", "false": "SEALED"},
    })
    value = {"graph": {"edges": [["a", "b"]], "directed": True}, "start": "a", "goal": "b"}
    assert program.run(value) == "OPEN"


def test_shortest_path_returns_none_when_unreachable() -> None:
    program = Program.parse({"kind": "shortest_path"})
    value = {"graph": {"edges": [["a", "b"]], "directed": True}, "start": "b", "goal": "a"}
    assert program.run(value) is None


def test_affine_transform() -> None:
    program = Program.parse({"kind": "affine", "a": -4, "b": 17})
    assert program.run(3) == 5


def test_digest_is_key_order_invariant() -> None:
    left = Program.parse({"kind": "affine", "a": 2, "b": 1})
    right = Program.parse({"b": 1, "a": 2, "kind": "affine"})
    assert left.digest == right.digest


def test_unknown_node_is_rejected() -> None:
    with pytest.raises(ValueError):
        Program.parse({"kind": "python", "code": "x"})


def test_step_bound_is_enforced() -> None:
    program = Program.parse({"kind": "compose", "parts": [{"kind": "input"}] * 4})
    with pytest.raises(BudgetExceeded):
        program.run(1, EngineLimits(max_steps=2))
