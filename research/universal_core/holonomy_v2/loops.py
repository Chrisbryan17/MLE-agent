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
    REWRITE_NORMAL_FORM = "REWRITE_NORMAL_FORM"
    VOTE_PERMUTATION = "VOTE_PERMUTATION"
    RAY_DIRECTION_SCALE = "RAY_DIRECTION_SCALE"
    MATCHING_PERMUTATION = "MATCHING_PERMUTATION"
    SPAN_TRANSLATION = "SPAN_TRANSLATION"
    BIT_ROTATION_EQUIVARIANCE = "BIT_ROTATION_EQUIVARIANCE"
    CYCLE_ROTATION = "CYCLE_ROTATION"
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
        for key, field in data.items():
            if (key == "field" or key.endswith("_field")) and isinstance(field, str):
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
            if (key == "field" or key.endswith("_field")) and isinstance(item, str):
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


def _state_cycles(data: Mapping[str, Any], limit: int = 8) -> tuple[tuple[Any, tuple[Any, ...]], ...]:
    transitions = list(data.get("transitions", ()))
    states: list[Any] = []
    for item in transitions:
        for state in (item["state"], item["next"]):
            if state not in states:
                states.append(state)
    cycles: list[tuple[Any, tuple[Any, ...]]] = []

    def walk(start: Any, state: Any, actions: tuple[Any, ...], visited: tuple[Any, ...]) -> None:
        if len(cycles) >= limit or len(actions) >= max(1, len(states)):
            return
        for item in transitions:
            if item["state"] != state:
                continue
            nxt = item["next"]
            next_actions = actions + (item["action"],)
            if nxt == start:
                candidate = (start, next_actions)
                if candidate not in cycles:
                    cycles.append(candidate)
                continue
            if nxt in visited:
                continue
            walk(start, nxt, next_actions, visited + (nxt,))

    for state in states:
        walk(state, state, (), (state,))
        if len(cycles) >= limit:
            break
    return tuple(cycles)


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

    if data.get("kind") == "state_fold" and demos:
        base_input, _ = _demo_parts(demos[0])
        if isinstance(base_input, Mapping):
            for index, (state, actions) in enumerate(_state_cycles(data)):
                cycle_input = deepcopy(dict(base_input))
                cycle_input[data["state_field"]] = deepcopy(state)
                cycle_input[data["actions_field"]] = list(deepcopy(actions))
                mandatory.append(ClosedPath(
                    LoopKind.STATE_CYCLE,
                    True,
                    cycle_input,
                    deepcopy(state),
                    data,
                    f"state-cycle-{index}",
                ))

    if data.get("kind") == "stack_rewrite":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            normal_input = deepcopy(dict(inp))
            normal_input[data["sequence_field"]] = deepcopy(expected)
            mandatory.append(ClosedPath(
                LoopKind.REWRITE_NORMAL_FORM,
                True,
                normal_input,
                deepcopy(expected),
                data,
                f"rewrite-normal-form-{index}",
            ))

    if data.get("kind") == "weighted_vote_veto" and data.get("tie_policy") == "lexicographic":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            ballots = inp.get(data["ballots_field"])
            if not isinstance(ballots, Sequence) or isinstance(ballots, (str, bytes, bytearray)):
                continue
            permuted_input = deepcopy(dict(inp))
            permuted_input[data["ballots_field"]] = list(reversed(deepcopy(ballots)))
            mandatory.append(ClosedPath(
                LoopKind.VOTE_PERMUTATION,
                True,
                permuted_input,
                deepcopy(expected),
                data,
                f"vote-permutation-{index}",
            ))

    if data.get("kind") == "ray_first_hit":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            direction = inp.get(data["direction_field"])
            if (
                not isinstance(direction, Sequence)
                or isinstance(direction, (str, bytes, bytearray))
                or not direction
                or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in direction)
            ):
                continue
            scaled_input = deepcopy(dict(inp))
            scaled_input[data["direction_field"]] = [item * 2 for item in direction]
            mandatory.append(ClosedPath(
                LoopKind.RAY_DIRECTION_SCALE,
                True,
                scaled_input,
                deepcopy(expected),
                data,
                f"ray-direction-scale-{index}",
            ))

    if data.get("kind") == "distinct_slot_match":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            items = inp.get(data["items_field"])
            if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
                continue
            changed_items = []
            valid = True
            for item in reversed(deepcopy(items)):
                if not isinstance(item, Mapping):
                    valid = False
                    break
                changed_item = deepcopy(dict(item))
                slots = changed_item.get(data["slots_field"])
                if not isinstance(slots, Sequence) or isinstance(slots, (str, bytes, bytearray)):
                    valid = False
                    break
                changed_item[data["slots_field"]] = list(reversed(deepcopy(slots)))
                changed_items.append(changed_item)
            if not valid:
                continue
            changed_input = deepcopy(dict(inp))
            changed_input[data["items_field"]] = changed_items
            mandatory.append(ClosedPath(
                LoopKind.MATCHING_PERMUTATION,
                True,
                changed_input,
                deepcopy(expected),
                data,
                f"matching-permutation-{index}",
            ))

    if data.get("kind") == "integer_span_cover":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            span_start = inp.get(data["span_start_field"])
            span_end = inp.get(data["span_end_field"])
            intervals = inp.get(data["intervals_field"])
            if (
                not isinstance(span_start, int)
                or isinstance(span_start, bool)
                or not isinstance(span_end, int)
                or isinstance(span_end, bool)
                or not isinstance(intervals, Sequence)
                or isinstance(intervals, (str, bytes, bytearray))
            ):
                continue
            shifted_intervals = []
            valid = True
            for interval in deepcopy(intervals):
                if not isinstance(interval, Mapping):
                    valid = False
                    break
                start = interval.get(data["interval_start_field"])
                end = interval.get(data["interval_end_field"])
                if (
                    not isinstance(start, int)
                    or isinstance(start, bool)
                    or not isinstance(end, int)
                    or isinstance(end, bool)
                ):
                    valid = False
                    break
                shifted = deepcopy(dict(interval))
                shifted[data["interval_start_field"]] = start + 7
                shifted[data["interval_end_field"]] = end + 7
                shifted_intervals.append(shifted)
            if not valid:
                continue
            shifted_input = deepcopy(dict(inp))
            shifted_input[data["span_start_field"]] = span_start + 7
            shifted_input[data["span_end_field"]] = span_end + 7
            shifted_input[data["intervals_field"]] = shifted_intervals
            mandatory.append(ClosedPath(
                LoopKind.SPAN_TRANSLATION,
                True,
                shifted_input,
                deepcopy(expected),
                data,
                f"span-translation-{index}",
            ))

    if data.get("kind") == "circular_bit_step":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            sequence = inp.get(data["sequence_field"])
            if isinstance(sequence, str):
                if not sequence or not isinstance(expected, str) or not expected:
                    continue
                rotated_sequence = sequence[1:] + sequence[:1]
                rotated_expected = expected[1:] + expected[:1]
            elif isinstance(sequence, Sequence) and not isinstance(sequence, (str, bytes, bytearray)):
                if not sequence or not isinstance(expected, Sequence) or isinstance(expected, (str, bytes, bytearray)) or not expected:
                    continue
                changed_sequence = list(sequence[1:]) + [sequence[0]]
                changed_expected = list(expected[1:]) + [expected[0]]
                rotated_sequence = tuple(changed_sequence) if isinstance(sequence, tuple) else changed_sequence
                rotated_expected = tuple(changed_expected) if isinstance(expected, tuple) else changed_expected
            else:
                continue
            rotated_input = deepcopy(dict(inp))
            rotated_input[data["sequence_field"]] = rotated_sequence
            mandatory.append(ClosedPath(
                LoopKind.BIT_ROTATION_EQUIVARIANCE,
                True,
                rotated_input,
                deepcopy(rotated_expected),
                data,
                f"bit-rotation-{index}",
            ))

    if data.get("kind") == "cyclic_skip_step":
        for index, demo in enumerate(demos[:3]):
            inp, expected = _demo_parts(demo)
            if not isinstance(inp, Mapping):
                continue
            cycle = inp.get(data["cycle_field"])
            if not isinstance(cycle, Sequence) or isinstance(cycle, (str, bytes, bytearray)) or not cycle:
                continue
            rotated_input = deepcopy(dict(inp))
            rotated_input[data["cycle_field"]] = list(deepcopy(cycle[1:])) + [deepcopy(cycle[0])]
            mandatory.append(ClosedPath(
                LoopKind.CYCLE_ROTATION,
                True,
                rotated_input,
                deepcopy(expected),
                data,
                f"cycle-rotation-{index}",
            ))

    if data.get("kind") == "compose":
        for index, demo in enumerate(demos[:3]):
            inp, _ = _demo_parts(demo)
            try:
                expected = program.run(inp)
            except Exception:
                continue
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
