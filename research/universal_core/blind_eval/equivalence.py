from __future__ import annotations
import math
from fractions import Fraction
from typing import Any
from universal_core.canonical import canonical_json_bytes
from .contracts import EquivalenceKind, EquivalenceRule


def _unordered(value: Any) -> tuple[bytes, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError("unordered equivalence requires a sequence")
    return tuple(sorted(canonical_json_bytes(item) for item in value))


def _fraction(value: Any) -> Fraction:
    if isinstance(value, bool): raise ValueError("boolean is not a rational number")
    if isinstance(value, (int, str)): return Fraction(value)
    if isinstance(value, float) and math.isfinite(value): return Fraction(str(value))
    raise ValueError("unsupported rational value")


def _edge_set(value: Any, directed: bool) -> frozenset[tuple[bytes, bytes]]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError("graph equivalence requires an edge sequence")
    edges=[]
    for edge in value:
        if not isinstance(edge,(list,tuple)) or len(edge)!=2: raise ValueError("graph edge must contain two endpoints")
        a,b=canonical_json_bytes(edge[0]),canonical_json_bytes(edge[1])
        if not directed and b<a: a,b=b,a
        edges.append((a,b))
    return frozenset(edges)


def answers_equivalent(prediction: Any, target: Any, rule: EquivalenceRule) -> bool:
    if rule.kind is EquivalenceKind.EXACT:
        return canonical_json_bytes(prediction)==canonical_json_bytes(target)
    if rule.kind is EquivalenceKind.CASEFOLD_STRING:
        return isinstance(prediction,str) and isinstance(target,str) and prediction.casefold()==target.casefold()
    if rule.kind is EquivalenceKind.UNORDERED_SEQUENCE:
        return _unordered(prediction)==_unordered(target)
    if rule.kind is EquivalenceKind.RATIONAL_NUMBER:
        return _fraction(prediction)==_fraction(target)
    if rule.kind is EquivalenceKind.NUMERIC_TOLERANCE:
        if isinstance(prediction,bool) or isinstance(target,bool): return False
        try: left,right=float(prediction),float(target)
        except (TypeError,ValueError): return False
        if not math.isfinite(left) or not math.isfinite(right): return False
        return math.isclose(left,right,rel_tol=rule.relative_tolerance,abs_tol=rule.absolute_tolerance)
    if rule.kind is EquivalenceKind.GRAPH_EDGE_SET:
        return _edge_set(prediction,rule.directed_graph)==_edge_set(target,rule.directed_graph)
    raise ValueError(f"unsupported equivalence kind: {rule.kind}")
