from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable, Mapping, Sequence

from .ir import ValueType

OperatorFunction = Callable[[Any, Mapping[str, Any]], Any]


@dataclass(frozen=True)
class OperatorDefinition:
    name: str
    input_types: tuple[ValueType, ...]
    output_type: ValueType
    execute: OperatorFunction
    cost: int = 1


class OperatorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, OperatorDefinition] = {}

    def register(self, definition: OperatorDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"operator already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def get(self, name: str) -> OperatorDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown operator: {name}") from exc

    def execute(self, name: str, value: Any, arguments: Mapping[str, Any] | None = None) -> Any:
        definition = self.get(name)
        return definition.execute(value, dict(arguments or {}))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "input_types": [item.value for item in definition.input_types],
                "output_type": definition.output_type.value,
                "cost": definition.cost,
            }
            for definition in (self._definitions[name] for name in self.names)
        ]


def _require_allowed(args: Mapping[str, Any], allowed: set[str], required: set[str] = set()) -> None:
    unknown = set(args) - allowed
    missing = required - set(args)
    if unknown:
        raise ValueError(f"unknown operator arguments: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing operator arguments: {sorted(missing)}")


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise TypeError("operator input must be a sequence")
    return list(value)


def _field(item: Any, field: Any) -> Any:
    if field is None:
        return item
    if isinstance(item, Mapping):
        if field not in item:
            raise KeyError(f"field not found: {field}")
        return item[field]
    if isinstance(item, Sequence) and not isinstance(item, str | bytes):
        if not isinstance(field, int):
            raise TypeError("sequence field must be an integer")
        return item[field]
    raise TypeError("field projection requires a mapping or sequence record")


def _identity(value: Any, args: Mapping[str, Any]) -> Any:
    _require_allowed(args, set())
    return value


def _sort_values(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, {"descending"})
    return sorted(_sequence(value), reverse=bool(args.get("descending", False)))


def _sort_records(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, {"field", "descending"}, {"field"})
    field = args["field"]
    return sorted(
        _sequence(value),
        key=lambda item: _field(item, field),
        reverse=bool(args.get("descending", False)),
    )


def _reverse(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, set())
    return list(reversed(_sequence(value)))


def _count(value: Any, args: Mapping[str, Any]) -> int:
    _require_allowed(args, set())
    if not isinstance(value, Sequence | Mapping | set | frozenset) or isinstance(value, str | bytes):
        raise TypeError("count input must be a collection")
    return len(value)


def _numbers(value: Any) -> list[Real]:
    items = _sequence(value)
    if any(not isinstance(item, Real) or isinstance(item, bool) for item in items):
        raise TypeError("operator input must contain only numbers")
    return items


def _sum_numbers(value: Any, args: Mapping[str, Any]) -> Real:
    _require_allowed(args, set())
    return sum(_numbers(value))


def _min_value(value: Any, args: Mapping[str, Any]) -> Any:
    _require_allowed(args, set())
    return min(_sequence(value))


def _max_value(value: Any, args: Mapping[str, Any]) -> Any:
    _require_allowed(args, set())
    return max(_sequence(value))


def _filter_equals(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, {"field", "value"}, {"value"})
    return [item for item in _sequence(value) if _field(item, args.get("field")) == args["value"]]


_COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
}


def _filter_compare(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, {"field", "comparison", "value"}, {"comparison", "value"})
    comparison = str(args["comparison"])
    if comparison not in _COMPARISONS:
        raise ValueError(f"unsupported comparison: {comparison}")
    predicate = _COMPARISONS[comparison]
    return [
        item
        for item in _sequence(value)
        if predicate(_field(item, args.get("field")), args["value"])
    ]


def _project_field(value: Any, args: Mapping[str, Any]) -> list[Any]:
    _require_allowed(args, {"field"}, {"field"})
    return [_field(item, args["field"]) for item in _sequence(value)]


def _group_by(value: Any, args: Mapping[str, Any]) -> dict[str, list[Any]]:
    _require_allowed(args, {"field"}, {"field"})
    groups: dict[str, list[Any]] = {}
    for item in _sequence(value):
        key = str(_field(item, args["field"]))
        groups.setdefault(key, []).append(item)
    return {key: groups[key] for key in sorted(groups)}


def _rank_records(value: Any, args: Mapping[str, Any]) -> list[dict[str, Any]]:
    _require_allowed(args, {"field", "descending"}, {"field"})
    ordered = _sort_records(value, args)
    return [{"rank": index + 1, "record": record} for index, record in enumerate(ordered)]


def _contains_token(value: Any, args: Mapping[str, Any]) -> bool:
    _require_allowed(args, {"token", "case_sensitive"}, {"token"})
    token = str(args["token"])
    case_sensitive = bool(args.get("case_sensitive", False))
    if isinstance(value, str):
        haystack = value if case_sensitive else value.casefold()
        needle = token if case_sensitive else token.casefold()
        return needle in haystack
    items = [str(item) for item in _sequence(value)]
    if not case_sensitive:
        items = [item.casefold() for item in items]
        token = token.casefold()
    return token in items


def _all_true(value: Any, args: Mapping[str, Any]) -> bool:
    _require_allowed(args, set())
    return all(_sequence(value))


def _any_true(value: Any, args: Mapping[str, Any]) -> bool:
    _require_allowed(args, set())
    return any(_sequence(value))


def _adjacency(value: Any) -> dict[Any, tuple[Any, ...]]:
    if not isinstance(value, Mapping):
        raise TypeError("graph input must be a mapping")
    edges = value.get("edges")
    if not isinstance(edges, Sequence) or isinstance(edges, str | bytes):
        raise TypeError("graph edges must be a sequence")
    directed = bool(value.get("directed", False))
    graph: dict[Any, set[Any]] = {}
    for edge in edges:
        if not isinstance(edge, Sequence) or isinstance(edge, str | bytes) or len(edge) != 2:
            raise TypeError("each graph edge must have two endpoints")
        left, right = edge
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set())
        if not directed:
            graph[right].add(left)
    return {node: tuple(sorted(neighbors, key=str)) for node, neighbors in graph.items()}


def _path_length(value: Any, args: Mapping[str, Any]) -> int | None:
    _require_allowed(args, {"start", "goal"}, {"start", "goal"})
    start, goal = args["start"], args["goal"]
    if start == goal:
        return 0
    graph = _adjacency(value)
    queue: deque[tuple[Any, int]] = deque([(start, 0)])
    visited = {start}
    while queue:
        node, distance = queue.popleft()
        for neighbor in graph.get(node, ()):
            if neighbor == goal:
                return distance + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    return None


def _graph_reachable(value: Any, args: Mapping[str, Any]) -> bool:
    return _path_length(value, args) is not None


def _shortest_path_length(value: Any, args: Mapping[str, Any]) -> int | None:
    return _path_length(value, args)


def _format_scalar(value: Any, args: Mapping[str, Any]) -> str:
    _require_allowed(args, {"prefix", "suffix", "format"})
    format_spec = str(args.get("format", ""))
    rendered = format(value, format_spec) if format_spec else str(value)
    return f"{args.get('prefix', '')}{rendered}{args.get('suffix', '')}"


def _definition(
    name: str,
    execute: OperatorFunction,
    output: ValueType,
    inputs: tuple[ValueType, ...] = (ValueType.UNKNOWN,),
    cost: int = 1,
) -> OperatorDefinition:
    return OperatorDefinition(name, inputs, output, execute, cost)


def default_registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    definitions = (
        _definition("identity", _identity, ValueType.UNKNOWN),
        _definition("sort_values", _sort_values, ValueType.LIST, (ValueType.LIST, ValueType.SET)),
        _definition("sort_records", _sort_records, ValueType.LIST, (ValueType.LIST, ValueType.TABLE)),
        _definition("reverse", _reverse, ValueType.LIST, (ValueType.LIST,)),
        _definition("count", _count, ValueType.INTEGER),
        _definition("sum_numbers", _sum_numbers, ValueType.NUMBER, (ValueType.LIST,)),
        _definition("min_value", _min_value, ValueType.UNKNOWN, (ValueType.LIST,)),
        _definition("max_value", _max_value, ValueType.UNKNOWN, (ValueType.LIST,)),
        _definition("filter_equals", _filter_equals, ValueType.LIST, (ValueType.LIST, ValueType.TABLE)),
        _definition("filter_compare", _filter_compare, ValueType.LIST, (ValueType.LIST, ValueType.TABLE)),
        _definition("project_field", _project_field, ValueType.LIST, (ValueType.LIST, ValueType.TABLE)),
        _definition("group_by", _group_by, ValueType.MAP, (ValueType.LIST, ValueType.TABLE)),
        _definition("rank_records", _rank_records, ValueType.LIST, (ValueType.LIST, ValueType.TABLE)),
        _definition("contains_token", _contains_token, ValueType.BOOLEAN),
        _definition("all_true", _all_true, ValueType.BOOLEAN, (ValueType.LIST,)),
        _definition("any_true", _any_true, ValueType.BOOLEAN, (ValueType.LIST,)),
        _definition("graph_reachable", _graph_reachable, ValueType.BOOLEAN, (ValueType.GRAPH,), cost=2),
        _definition("shortest_path_length", _shortest_path_length, ValueType.INTEGER, (ValueType.GRAPH,), cost=2),
        _definition("format_scalar", _format_scalar, ValueType.STRING),
        _definition("return_value", _identity, ValueType.UNKNOWN),
    )
    for definition in definitions:
        registry.register(definition)
    return registry
