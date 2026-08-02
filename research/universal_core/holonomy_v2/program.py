from __future__ import annotations

import hashlib
import itertools
import json
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from numbers import Real
from typing import Any, Mapping, Sequence

from .types import EngineLimits, NodeKind


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class EvaluationContext:
    limits: EngineLimits
    steps: int = 0

    def tick(self, count: int = 1) -> None:
        self.steps += count
        if self.steps > self.limits.max_steps:
            raise BudgetExceeded("program step bound exceeded")


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _compare(left: Any, op: str, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "in":
        return left in right
    if op == "contains":
        return right in left
    raise ValueError(f"unknown comparison: {op}")


def _graph_parts(value: Mapping[str, Any]) -> tuple[list[tuple[Any, Any]], Any, Any, bool]:
    graph = value.get("graph", value)
    if not isinstance(graph, Mapping):
        raise TypeError("graph must be a mapping")
    edges = [tuple(edge) for edge in graph.get("edges", ())]
    start = value.get("start")
    goal = value.get("goal")
    directed = bool(graph.get("directed", True))
    return edges, start, goal, directed


def _shortest_path(value: Mapping[str, Any]) -> int | None:
    edges, start, goal, directed = _graph_parts(value)
    links: dict[Any, list[Any]] = {}
    for left, right in edges:
        links.setdefault(left, []).append(right)
        links.setdefault(right, [])
        if not directed:
            links[right].append(left)
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        node, depth = queue.popleft()
        if node == goal:
            return depth
        for nxt in links.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return None


def _field(value: Any, name: Any) -> Any:
    if isinstance(value, Mapping):
        return value[name]
    return value[name]


_ALLOWED = {item.value for item in NodeKind}


@dataclass(frozen=True)
class Program:
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        normalized = _normalize(self.data)
        _validate(normalized)
        object.__setattr__(self, "data", normalized)

    @classmethod
    def parse(cls, data: Mapping[str, Any]) -> "Program":
        return cls(deepcopy(dict(data)))

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_bytes(self.data)).hexdigest()

    @property
    def cost(self) -> int:
        return _cost(self.data)

    def to_data(self) -> dict[str, Any]:
        return deepcopy(dict(self.data))

    def run(self, value: Any, limits: EngineLimits | None = None) -> Any:
        context = EvaluationContext(limits or EngineLimits())
        return _run(self.data, value, context)


def _validate(data: Mapping[str, Any]) -> None:
    kind = data.get("kind")
    if kind not in _ALLOWED:
        raise ValueError(f"unknown node kind: {kind}")
    if kind == "compose":
        parts = data.get("parts")
        if not isinstance(parts, Sequence) or isinstance(parts, (str, bytes)) or not parts:
            raise ValueError("compose requires nonempty parts")
        for part in parts:
            if not isinstance(part, Mapping):
                raise TypeError("program part must be a mapping")
            _validate(part)
    for key in ("source", "if", "then", "else", "item"):
        child = data.get(key)
        if isinstance(child, Mapping) and "kind" in child:
            _validate(child)
    if kind in {"filter", "compare"} and data.get("comparison") not in {"==", "!=", "<", "<=", ">", ">=", "in", "contains"}:
        raise ValueError("invalid comparison")
    if kind == "aggregate" and data.get("op") not in {"sum", "count", "min", "max"}:
        raise ValueError("invalid aggregate operation")


def _cost(data: Mapping[str, Any]) -> int:
    base = 1
    if data["kind"] == "compose":
        return base + sum(_cost(part) for part in data["parts"])
    return base + sum(
        _cost(value)
        for key, value in data.items()
        if key in {"source", "if", "then", "else", "item"} and isinstance(value, Mapping) and "kind" in value
    )


def _run(data: Mapping[str, Any], value: Any, context: EvaluationContext) -> Any:
    context.tick()
    kind = data["kind"]
    if kind == "input":
        return value
    if kind == "literal":
        return deepcopy(data.get("value"))
    if kind == "field":
        source = _run(data["source"], value, context) if "source" in data else value
        return _field(source, data["field"])
    if kind == "index":
        source = _run(data["source"], value, context) if "source" in data else value
        return source[int(data["index"])]
    if kind == "compose":
        current = value
        for part in data["parts"]:
            current = _run(part, current, context)
        return current
    if kind == "map":
        source = _run(data["source"], value, context) if "source" in data else value
        return [_run(data["item"], item, context) for item in source]
    if kind == "filter":
        source = _run(data["source"], value, context) if "source" in data else value
        field_name = data.get("field")
        right = data.get("value")
        op = data["comparison"]
        return [item for item in source if _compare(_field(item, field_name) if field_name is not None else item, op, right)]
    if kind == "project":
        source = _run(data["source"], value, context) if "source" in data else value
        field_name = data["field"]
        if isinstance(source, Mapping):
            return source[field_name]
        return [_field(item, field_name) for item in source]
    if kind == "order":
        source = _run(data["source"], value, context) if "source" in data else value
        field_name = data.get("field")
        key = (lambda item: _field(item, field_name)) if field_name is not None else None
        return sorted(source, key=key, reverse=bool(data.get("descending", False)))
    if kind == "aggregate":
        source = _run(data["source"], value, context) if "source" in data else value
        field_name = data.get("field")
        items = [_field(item, field_name) for item in source] if field_name is not None else list(source)
        op = data["op"]
        if op == "count":
            return len(items)
        if op == "sum":
            return sum(items)
        if op == "min":
            return min(items)
        if op == "max":
            return max(items)
        raise ValueError("invalid aggregate operation")
    if kind == "compare":
        if "left" in data:
            left = _run(data["left"], value, context) if isinstance(data["left"], Mapping) else data["left"]
        elif "field" in data:
            left = _field(value, data["field"])
        else:
            left = value
        right_data = data.get("right", data.get("value"))
        right = _run(right_data, value, context) if isinstance(right_data, Mapping) and "kind" in right_data else right_data
        return _compare(left, data["comparison"], right)
    if kind == "boolean":
        op = data["op"]
        terms = [_run(term, value, context) for term in data.get("terms", ())]
        if op == "and":
            return all(terms)
        if op == "or":
            return any(terms)
        if op == "not":
            if len(terms) != 1:
                raise ValueError("not requires one term")
            return not terms[0]
        raise ValueError("invalid boolean operation")
    if kind == "conditional":
        branch = data["then"] if _run(data["if"], value, context) else data["else"]
        return _run(branch, value, context)
    if kind == "label_map":
        source = _run(data["source"], value, context)
        key = str(source).lower() if isinstance(source, bool) else str(source)
        mapping = data["mapping"]
        if key in mapping:
            return mapping[key]
        if "default" in data:
            return data["default"]
        raise KeyError(key)
    if kind == "graph_reachable":
        if not isinstance(value, Mapping):
            raise TypeError("graph input must be a mapping")
        return _shortest_path(value) is not None
    if kind == "shortest_path":
        if not isinstance(value, Mapping):
            raise TypeError("graph input must be a mapping")
        return _shortest_path(value)
    if kind == "format":
        source = _run(data["source"], value, context) if "source" in data else value
        return str(data["template"]).format(value=source)
    if kind == "affine":
        if not isinstance(value, Real) or isinstance(value, bool):
            raise TypeError("affine input must be numeric")
        a = Fraction(str(data["a"]))
        b = Fraction(str(data["b"]))
        result = a * Fraction(str(value)) + b
        return result.numerator if result.denominator == 1 else float(result)
    if kind == "token_map":
        text = str(value)
        tokens = text.split()
        for token, label in data["mapping"].items():
            if token in tokens:
                return label
        if "default" in data:
            return data["default"]
        raise KeyError("no token matched")
    if kind in {"modular_symbol", "priority_rules", "grid_pattern_count", "resource_makespan"}:
        raise NotImplementedError(kind)
    raise ValueError(f"unsupported node kind: {kind}")
