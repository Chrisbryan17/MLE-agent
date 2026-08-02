from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .loops import LoopKind


@dataclass(frozen=True)
class Counterexample:
    kind: LoopKind
    note: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class Refinement:
    state_fields: tuple[str, ...] = ()
    priority_edges: tuple[tuple[str, str], ...] = ()
    rejected_inverses: tuple[str, ...] = ()
    activate_bounded_search: bool = False
    reason: str = ""


def refine_from_counterexample(item: Counterexample) -> Refinement:
    if item.kind is LoopKind.STATE_CYCLE and isinstance(item.details.get("context_field"), str):
        return Refinement(
            state_fields=(str(item.details["context_field"]),),
            reason="context-dependent transport",
        )
    if item.kind is LoopKind.PRIORITY_AGREEMENT:
        higher = item.details.get("higher")
        lower = item.details.get("lower")
        if isinstance(higher, str) and isinstance(lower, str):
            return Refinement(priority_edges=((higher, lower),), reason="priority path disagreement")
    if item.details.get("requires_bounded_search") is True:
        return Refinement(activate_bounded_search=True, reason="finite search required")
    inverse = item.details.get("inverse_digest")
    if isinstance(inverse, str):
        return Refinement(rejected_inverses=(inverse,), reason="invalid inverse transport")
    return Refinement(reason="no grammar change")
