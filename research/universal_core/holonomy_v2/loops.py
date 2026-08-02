from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .grammar import TaskGrammar
from .program import Program


class LoopKind(str, Enum):
    DEMONSTRATION_REPLAY = "DEMONSTRATION_REPLAY"
    PATH_AGREEMENT = "PATH_AGREEMENT"
    KEY_RENAME_ROUND_TRIP = "KEY_RENAME_ROUND_TRIP"
    KEY_PERMUTATION_ROUND_TRIP = "KEY_PERMUTATION_ROUND_TRIP"
    ROW_PERMUTATION = "ROW_PERMUTATION"
    DEMO_REORDER = "DEMO_REORDER"
    ADAPTER_ROUND_TRIP = "ADAPTER_ROUND_TRIP"
    STATE_CYCLE = "STATE_CYCLE"
    PRIORITY_AGREEMENT = "PRIORITY_AGREEMENT"


@dataclass(frozen=True)
class ClosedPath:
    kind: LoopKind
    mandatory: bool
    input_value: Any
    expected: Any
    program_data: Mapping[str, Any]
    note: str = ""


@dataclass(frozen=True)
class LoopSet:
    mandatory: tuple[ClosedPath, ...]
    optional: tuple[ClosedPath, ...]

    @property
    def all(self) -> tuple[ClosedPath, ...]:
        return self.mandatory + self.optional


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise TypeError("demonstration must provide input and output")


def _field_names(data: Any) -> tuple[str, ...]:
    found: set[str] = set()
    if isinstance(data, Mapping):
        field = data.get("field")
        if isinstance(field, str):
            found.add(field)
        for value in data.values():
            found.update(_field_names(value))
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        for item in data:
            found.update(_field_names(item))
    return tuple(sorted(found))


def _rename_value(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {
            mapping.get(str(key), str(key)): _rename_value(item, mapping)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rename_value(item, mapping) for item in value]
    if isinstance(value, tuple):
        return tuple(_rename_value(item, mapping) for item in value)
    return deepcopy(value)


def _rename_program(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "field" and isinstance(item, str):
                result[key] = mapping.get(item, item)
            else:
                result[key] = _rename_program(item, mapping)
        return result
    if isinstance(value, list):
        return [_rename_program(item, mapping) for item in value]
    return deepcopy(value)


def _permute_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _permute_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_permute_keys(item) for item in value]
    return deepcopy(value)


def _contains_kind(data: Any, kinds: set[str]) -> bool:
    if isinstance(data, Mapping):
        if data.get("kind") in kinds:
            return True
        return any(_contains_kind(value, kinds) for value in data.values())
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return any(_contains_kind(item, kinds) for item in data)
    return False


def build_loops(
    program: Program,
    demonstrations: Iterable[Any],
    grammar: TaskGrammar,
) -> LoopSet:
    del grammar
    demos = tuple(demonstrations)
    mandatory: list[ClosedPath] = []
    optional: list[ClosedPath] = []
    data = program.to_data()

    for index, demo in enumerate(demos):
        inp, expected = _demo_parts(demo)
        mandatory.append(ClosedPath(
            LoopKind.DEMONSTRATION_REPLAY,
            True,
            deepcopy(inp),
            deepcopy(expected),
            data,
            f"demo-{index}",
        ))

    if data.get("kind") == "compose":
        for index, demo in enumerate(demos[:3]):
            inp, _ = _demo_parts(demo)
            expected = program.run(inp)
            mandatory.append(ClosedPath(
                LoopKind.PATH_AGREEMENT,
                True,
                deepcopy(inp),
                deepcopy(expected),
                data,
                f"composed-path-{index}",
            ))

    names = _field_names(data)
    if names and demos:
        mapping = {name: f"f{index}" for index, name in enumerate(names)}
        inp, expected = _demo_parts(demos[0])
        mandatory.append(ClosedPath(
            LoopKind.KEY_RENAME_ROUND_TRIP,
            True,
            _rename_value(inp, mapping),
            _rename_value(expected, mapping),
            _rename_program(data, mapping),
            "alpha-renamed fields",
        ))
        optional.append(ClosedPath(
            LoopKind.ADAPTER_ROUND_TRIP,
            False,
            _rename_value(inp, mapping),
            _rename_value(expected, mapping),
            _rename_program(data, mapping),
            "field adapter round trip",
        ))

    if demos:
        inp, expected = _demo_parts(demos[0])
        permuted = _permute_keys(inp)
        mandatory.append(ClosedPath(
            LoopKind.KEY_PERMUTATION_ROUND_TRIP,
            True,
            permuted,
            deepcopy(expected),
            data,
            "record key order changed",
        ))
        if isinstance(inp, list) and _contains_kind(data, {"order", "aggregate", "filter"}):
            optional.append(ClosedPath(
                LoopKind.ROW_PERMUTATION,
                False,
                list(reversed(deepcopy(inp))),
                deepcopy(expected),
                data,
                "input row order changed",
            ))

    for index, demo in enumerate(reversed(demos[:3])):
        inp, expected = _demo_parts(demo)
        optional.append(ClosedPath(
            LoopKind.DEMO_REORDER,
            False,
            deepcopy(inp),
            deepcopy(expected),
            data,
            f"reordered-demo-{index}",
        ))

    return LoopSet(tuple(mandatory), tuple(optional))
