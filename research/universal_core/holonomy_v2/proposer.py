from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from .fibers import FiberSchema
from .program import Program
from .types import NodeKind


class ProposalError(ValueError):
    pass


@dataclass(frozen=True)
class ProgramProposal:
    program: Program
    rationale: str
    confidence: float
    declared_constants: tuple[Any, ...]


class ProposalBackend(Protocol):
    def propose(
        self,
        instructions: str,
        demonstrations: tuple[Any, ...],
        allowed_constants: tuple[Any, ...],
    ) -> tuple[ProgramProposal, ...]: ...


_NODE_FIELDS: dict[str, frozenset[str]] = {
    "input": frozenset({"kind"}),
    "literal": frozenset({"kind", "value"}),
    "field": frozenset({"kind", "field", "source"}),
    "index": frozenset({"kind", "index", "source"}),
    "compose": frozenset({"kind", "parts"}),
    "map": frozenset({"kind", "source", "item"}),
    "filter": frozenset({"kind", "source", "field", "comparison", "value"}),
    "project": frozenset({"kind", "source", "field"}),
    "order": frozenset({"kind", "source", "field", "descending"}),
    "aggregate": frozenset({"kind", "source", "field", "op"}),
    "compare": frozenset({"kind", "left", "right", "field", "comparison", "value"}),
    "boolean": frozenset({"kind", "op", "terms"}),
    "conditional": frozenset({"kind", "if", "then", "else"}),
    "label_map": frozenset({"kind", "source", "mapping", "default"}),
    "graph_reachable": frozenset({"kind"}),
    "shortest_path": frozenset({"kind"}),
    "format": frozenset({"kind", "source", "template"}),
    "affine": frozenset({"kind", "a", "b"}),
    "token_map": frozenset({"kind", "mapping", "default"}),
    "modular_symbol": frozenset({"kind", "cycle", "terms", "modulus"}),
    "priority_rules": frozenset({"kind", "rules", "default"}),
    "grid_pattern_count": frozenset({"kind", "board_field", "player_field", "empty", "directions"}),
    "resource_makespan": frozenset({"kind", "jobs_field", "edges_field", "id_field", "duration_field", "resource_field"}),
}


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise ProposalError("demonstration must provide input and output")


def _walk_nodes(value: Any) -> None:
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if kind is not None:
            allowed = _NODE_FIELDS.get(str(kind))
            if allowed is None:
                raise ProposalError(f"unknown node kind: {kind}")
            extra = set(value) - allowed
            if extra:
                raise ProposalError(f"extra node fields: {sorted(extra)}")
        for item in value.values():
            _walk_nodes(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _walk_nodes(item)


def _program_constants(data: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(data, Mapping):
        kind = data.get("kind")
        if kind == "literal":
            values.append(data.get("value"))
        elif kind == "affine":
            values.extend((data.get("a"), data.get("b")))
        elif kind == "filter":
            values.append(data.get("value"))
        for key, item in data.items():
            if key not in {"value", "a", "b"}:
                values.extend(_program_constants(item))
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        for item in data:
            values.extend(_program_constants(item))
    return values


def _contains(items: tuple[Any, ...], value: Any) -> bool:
    return any(item == value and type(item) is type(value) for item in items)


class JsonProposalBackend:
    def __init__(self, source: Callable[[Mapping[str, Any]], Any]) -> None:
        self._source = source

    def propose(
        self,
        instructions: str,
        demonstrations: tuple[Any, ...],
        allowed_constants: tuple[Any, ...],
    ) -> tuple[ProgramProposal, ...]:
        request = {
            "instructions": instructions,
            "demonstrations": [
                {"input": _demo_parts(item)[0], "output": _demo_parts(item)[1]}
                for item in demonstrations
            ],
            "allowed_constants": list(allowed_constants),
            "allowed_node_kinds": sorted(item.value for item in NodeKind),
        }
        raw = self._source(request)
        items = raw if isinstance(raw, list) else [raw]
        proposals: list[ProgramProposal] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise ProposalError("proposal must be a mapping")
            expected = {"program", "rationale", "confidence", "declared_constants"}
            if set(item) != expected:
                raise ProposalError("proposal fields do not match the contract")
            confidence = float(item["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise ProposalError("confidence must be between zero and one")
            declared = tuple(item["declared_constants"])
            if any(not _contains(allowed_constants, value) for value in declared):
                raise ProposalError("declared constant is not allowed")
            data = item["program"]
            if not isinstance(data, Mapping):
                raise ProposalError("program must be a mapping")
            _walk_nodes(data)
            for value in _program_constants(data):
                if not _contains(declared, value):
                    raise ProposalError("program uses an undeclared constant")
            program = Program.parse(data)
            expected_schema = FiberSchema.infer(_demo_parts(demonstrations[0])[1])
            for demo in demonstrations:
                inp, expected_output = _demo_parts(demo)
                try:
                    actual = program.run(inp)
                except Exception as exc:
                    raise ProposalError(f"proposal execution failed: {type(exc).__name__}") from exc
                if FiberSchema.infer(actual) != expected_schema:
                    raise ProposalError("proposal output type mismatch")
                if actual != expected_output:
                    raise ProposalError("proposal does not replay demonstrations")
            proposals.append(ProgramProposal(program, str(item["rationale"]), confidence, declared))
        return tuple(proposals)
