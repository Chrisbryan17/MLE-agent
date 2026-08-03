from dataclasses import dataclass
from typing import Any

import pytest

from universal_core.holonomy_v2.engine import HolonomyEngine
from universal_core.holonomy_v2.proposer import JsonProposalBackend, ProposalError
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def _backend(data: Any) -> JsonProposalBackend:
    return JsonProposalBackend(lambda request: data)


def test_unknown_node_kind_is_rejected() -> None:
    backend = _backend({
        "program": {"kind": "foreign_code", "body": "x"},
        "rationale": "bad",
        "confidence": 0.5,
        "declared_constants": [],
    })
    with pytest.raises(ProposalError):
        backend.propose("Return input.", (Demo(1, 1),), ())


def test_extra_node_field_is_rejected() -> None:
    backend = _backend({
        "program": {"kind": "affine", "a": 2, "b": 1, "escape": True},
        "rationale": "bad field",
        "confidence": 0.5,
        "declared_constants": [1, 2],
    })
    with pytest.raises(ProposalError):
        backend.propose("Return 2*n+1.", (Demo(1, 3), Demo(2, 5)), (1, 2))


def test_undeclared_constant_is_rejected() -> None:
    backend = _backend({
        "program": {"kind": "affine", "a": 7, "b": 91},
        "rationale": "hidden constant",
        "confidence": 0.8,
        "declared_constants": [7],
    })
    with pytest.raises(ProposalError):
        backend.propose("Return 7*n plus a value.", (Demo(1, 98),), (7,))


def test_type_mismatch_is_rejected() -> None:
    backend = _backend({
        "program": {"kind": "literal", "value": "wrong"},
        "rationale": "wrong output type",
        "confidence": 0.8,
        "declared_constants": ["wrong"],
    })
    with pytest.raises(ProposalError):
        backend.propose("Return a number.", (Demo(1, 2), Demo(2, 3)), ("wrong",))


def test_valid_proposal_passes_same_closed_paths() -> None:
    backend = _backend({
        "program": {"kind": "affine", "a": 2, "b": 1},
        "rationale": "typed arithmetic",
        "confidence": 0.9,
        "declared_constants": [1, 2],
    })
    engine = HolonomyEngine(SearchConfig(tier="H"))
    result = engine.induce_with_proposer(
        "Return 2*n+1.",
        (Demo(1, 3), Demo(2, 5), Demo(3, 7)),
        backend,
    )
    assert result.program is not None
    assert result.report is not None and result.report.mandatory_pass
    assert result.evidence.tier == "H"
    assert engine.freeze(result).predict_all((4,)).predictions[0]["prediction"] == 9
