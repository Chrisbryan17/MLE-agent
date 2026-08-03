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



def _condition_matches(data: Mapping[str, Any], value: Mapping[str, Any]) -> bool:
    op = data.get("op")
    if op == "and":
        return all(_condition_matches(item, value) for item in data.get("terms", ()))
    if op == "or":
        return any(_condition_matches(item, value) for item in data.get("terms", ()))
    if op == "not":
        return not _condition_matches(data["term"], value)
    if "field" in data:
        observed = value[data["field"]]
        if "equals" in data:
            return observed == data["equals"]
        if "comparison" in data:
            return _compare(observed, data["comparison"], data.get("value"))
    raise ValueError("invalid rule condition")


def _grid_count(data: Mapping[str, Any], value: Mapping[str, Any]) -> int:
    board = value[data["board_field"]]
    actor = value[data["actor_field"]]
    empty = data.get("empty", ".")
    symbols = sorted({cell for row in board for cell in row if cell not in {actor, empty}})
    if len(symbols) != 1:
        raise ValueError("grid requires one opposing symbol")
    opponent = symbols[0]
    size = len(board)
    jump = int(data.get("jump", 2))
    directions = [tuple(item) for item in data.get("directions", ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    total = 0
    for row in range(size):
        for col in range(len(board[row])):
            if board[row][col] != actor:
                continue
            for dr, dc in directions:
                mid_row, mid_col = row + dr, col + dc
                end_row, end_col = row + jump * dr, col + jump * dc
                if not (0 <= end_row < size and 0 <= end_col < len(board[end_row])):
                    continue
                if board[mid_row][mid_col] == opponent and board[end_row][end_col] == empty:
                    total += 1
    return total


def _state_fold(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    transitions = data["transitions"]
    if len(transitions) > context.limits.max_state_count:
        raise BudgetExceeded("transition count exceeds configured bound")
    table = {
        _canonical_bytes([item["state"], item["action"]]): item["next"]
        for item in transitions
    }
    state = value[data["state_field"]]
    actions = value[data["actions_field"]]
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes, bytearray)):
        raise TypeError("state-fold actions must be a sequence")
    for action in actions:
        context.tick()
        key = _canonical_bytes([state, action])
        if key in table:
            state = deepcopy(table[key])
        elif data.get("unknown") == "identity":
            continue
        else:
            raise KeyError((state, action))
    return state



def _stack_tokens(value: Any, mode: str) -> tuple[list[Any], str]:
    if mode == "characters":
        if not isinstance(value, str):
            raise TypeError("character stack input must be a string")
        return list(value), "characters"
    if mode == "words":
        if not isinstance(value, str):
            raise TypeError("word stack input must be a string")
        return value.split(), "words"
    if mode == "items":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise TypeError("item stack input must be a sequence")
        return list(value), "tuple" if isinstance(value, tuple) else "items"
    raise ValueError("invalid stack token mode")


def _stack_output(stack: list[Any], output_mode: str) -> Any:
    if output_mode == "characters":
        if not all(isinstance(item, str) for item in stack):
            raise TypeError("character rewrite produced a non-string token")
        return "".join(stack)
    if output_mode == "words":
        if not all(isinstance(item, str) for item in stack):
            raise TypeError("word rewrite produced a non-string token")
        return " ".join(stack)
    if output_mode == "tuple":
        return tuple(stack)
    return stack


def _stack_rewrite(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    rules = data["rules"]
    if len(rules) > context.limits.max_state_count:
        raise BudgetExceeded("rewrite rule count exceeds configured bound")
    stack: list[Any] = []
    tokens, output_mode = _stack_tokens(value[data["sequence_field"]], data["token_mode"])
    for token in tokens:
        context.tick()
        stack.append(deepcopy(token))
        while True:
            matched = False
            for rule in rules:
                left = rule["left"]
                if len(left) <= len(stack) and stack[-len(left):] == left:
                    context.tick()
                    del stack[-len(left):]
                    stack.extend(deepcopy(rule["right"]))
                    matched = True
                    break
            if not matched:
                break
    return _stack_output(stack, output_mode)



def _weighted_support(value: Any) -> Fraction:
    if isinstance(value, bool):
        return Fraction(1 if value else -1)
    if isinstance(value, Real):
        return Fraction(str(value))
    raise TypeError("weighted support must be boolean or numeric")


def _weighted_vote_veto(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    ballots = value[data["ballots_field"]]
    if not isinstance(ballots, Sequence) or isinstance(ballots, (str, bytes, bytearray)):
        raise TypeError("ballots must be a sequence")
    if len(ballots) > context.limits.max_state_count:
        raise BudgetExceeded("ballot count exceeds configured bound")

    scores: dict[bytes, Fraction] = {}
    choices: dict[bytes, Any] = {}
    order: list[bytes] = []
    vetoed: set[bytes] = set()
    for ballot in ballots:
        context.tick()
        if not isinstance(ballot, Mapping):
            raise TypeError("ballot must be a mapping")
        choice = ballot[data["choice_field"]]
        key = _canonical_bytes(choice)
        if key not in choices:
            choices[key] = deepcopy(choice)
            scores[key] = Fraction(0)
            order.append(key)
        weight = ballot[data["weight_field"]]
        if not isinstance(weight, Real) or isinstance(weight, bool):
            raise TypeError("ballot weight must be numeric")
        weight_value = Fraction(str(weight))
        if weight_value < 0:
            raise ValueError("ballot weight must be nonnegative")
        veto = ballot[data["veto_field"]]
        if not isinstance(veto, bool):
            raise TypeError("ballot veto must be boolean")
        if veto:
            vetoed.add(key)
        scores[key] += weight_value * _weighted_support(ballot[data["support_field"]])

    threshold = Fraction(str(data["threshold"]))
    eligible = [key for key in order if key not in vetoed and scores[key] >= threshold]
    if not eligible:
        return deepcopy(data["default"])
    best_score = max(scores[key] for key in eligible)
    tied = [key for key in eligible if scores[key] == best_score]
    policy = data["tie_policy"]
    if len(tied) > 1 and policy == "error":
        raise ValueError("weighted vote tie")
    if policy == "first":
        winner = min(tied, key=order.index)
    else:
        winner = min(tied)
    return deepcopy(choices[winner])


def _numeric_vector(value: Any, name: str) -> list[Fraction]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or not value:
        raise ValueError(f"{name} must be a nonempty numeric sequence")
    result: list[Fraction] = []
    for item in value:
        if not isinstance(item, Real) or isinstance(item, bool):
            raise TypeError(f"{name} must contain only numbers")
        result.append(Fraction(str(item)))
    return result


def _ray_box_distance(
    origin: Sequence[Fraction],
    direction: Sequence[Fraction],
    lower: Sequence[Fraction],
    upper: Sequence[Fraction],
    context: EvaluationContext,
) -> Fraction | None:
    entered = Fraction(0)
    exited: Fraction | None = None
    for position, delta, low, high in zip(origin, direction, lower, upper):
        context.tick()
        if low > high:
            raise ValueError("box minimum exceeds maximum")
        if delta == 0:
            if position < low or position > high:
                return None
            continue
        first = (low - position) / delta
        second = (high - position) / delta
        near = min(first, second)
        far = max(first, second)
        entered = max(entered, near)
        exited = far if exited is None else min(exited, far)
        if exited < entered:
            return None
    if exited is None or exited < 0:
        return None
    return max(entered, Fraction(0))


def _ray_first_hit(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    origin = _numeric_vector(value[data["origin_field"]], "ray origin")
    direction = _numeric_vector(value[data["direction_field"]], "ray direction")
    if len(origin) != len(direction):
        raise ValueError("ray origin and direction dimensions differ")
    if all(item == 0 for item in direction):
        raise ValueError("ray direction must be nonzero")

    objects = value[data["objects_field"]]
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes, bytearray)):
        raise TypeError("ray objects must be a sequence")
    if len(objects) > context.limits.max_state_count:
        raise BudgetExceeded("object count exceeds configured bound")

    best_distance: Fraction | None = None
    tied: list[tuple[int, bytes, Any]] = []
    for index, item in enumerate(objects):
        context.tick()
        if not isinstance(item, Mapping):
            raise TypeError("ray object must be a mapping")
        lower = _numeric_vector(item[data["min_field"]], "box minimum")
        upper = _numeric_vector(item[data["max_field"]], "box maximum")
        if len(lower) != len(origin) or len(upper) != len(origin):
            raise ValueError("box and ray dimensions differ")
        distance = _ray_box_distance(origin, direction, lower, upper, context)
        if distance is None:
            continue
        identifier = item[data["id_field"]]
        entry = (index, _canonical_bytes(identifier), deepcopy(identifier))
        if best_distance is None or distance < best_distance:
            best_distance = distance
            tied = [entry]
        elif distance == best_distance:
            tied.append(entry)

    if not tied:
        return deepcopy(data["default"])
    policy = data["tie_policy"]
    if len(tied) > 1 and policy == "error":
        raise ValueError("ray first-hit tie")
    if policy == "first":
        winner = min(tied, key=lambda item: item[0])
    else:
        winner = min(tied, key=lambda item: item[1])
    return deepcopy(winner[2])



def _distinct_slot_match(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    items = value[data["items_field"]]
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must be a sequence")
    if len(items) > context.limits.max_state_count:
        raise BudgetExceeded("item count exceeds configured bound")

    adjacency: dict[bytes, tuple[bytes, ...]] = {}
    all_slots: set[bytes] = set()
    for item in items:
        context.tick()
        if not isinstance(item, Mapping):
            raise TypeError("item must be a mapping")
        item_key = _canonical_bytes(item[data["id_field"]])
        if item_key in adjacency:
            raise ValueError("duplicate item id")
        slots = item[data["slots_field"]]
        if not isinstance(slots, Sequence) or isinstance(slots, (str, bytes, bytearray)):
            raise TypeError("slots must be a sequence")
        slot_keys = tuple(sorted({_canonical_bytes(slot) for slot in slots}))
        adjacency[item_key] = slot_keys
        all_slots.update(slot_keys)

    if len(all_slots) > context.limits.max_state_count:
        raise BudgetExceeded("slot count exceeds configured bound")

    owner: dict[bytes, bytes] = {}

    def place(item_key: bytes, seen: set[bytes]) -> bool:
        for slot_key in adjacency[item_key]:
            context.tick()
            if slot_key in seen:
                continue
            seen.add(slot_key)
            prior = owner.get(slot_key)
            if prior is None or place(prior, seen):
                owner[slot_key] = item_key
                return True
        return False

    for item_key in sorted(adjacency):
        if not place(item_key, set()):
            return deepcopy(data["failure"])
    return deepcopy(data["success"])



def _integer_endpoint(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be integers")
    return value


def _integer_span_cover(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    span_start = _integer_endpoint(value[data["span_start_field"]], "span endpoints")
    span_end = _integer_endpoint(value[data["span_end_field"]], "span endpoints")
    if span_start > span_end:
        raise ValueError("span start must not exceed span end")

    intervals = value[data["intervals_field"]]
    if not isinstance(intervals, Sequence) or isinstance(intervals, (str, bytes, bytearray)):
        raise TypeError("intervals must be a sequence")
    if len(intervals) > context.limits.max_state_count:
        raise BudgetExceeded("interval count exceeds configured bound")

    ordered: list[tuple[int, int]] = []
    for interval in intervals:
        context.tick()
        if not isinstance(interval, Mapping):
            raise TypeError("interval must be a mapping")
        start = _integer_endpoint(interval[data["interval_start_field"]], "interval endpoints")
        end = _integer_endpoint(interval[data["interval_end_field"]], "interval endpoints")
        if start > end:
            raise ValueError("interval start must not exceed interval end")
        ordered.append((start, end))
    ordered.sort(key=lambda item: (item[0], -item[1]))

    position = span_start
    index = 0
    count = 0
    covered = True
    while position <= span_end:
        context.tick()
        farthest = position - 1
        while index < len(ordered) and ordered[index][0] <= position:
            context.tick()
            farthest = max(farthest, ordered[index][1])
            index += 1
        if farthest < position:
            covered = False
            break
        count += 1
        position = farthest + 1

    if data["mode"] == "minimum_count":
        return count if covered else deepcopy(data["failure"])
    return deepcopy(data["success"] if covered else data["failure"])



def _circular_bit_step(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    raw = value[data["sequence_field"]]
    mode = data["token_mode"]
    if mode == "characters":
        if not isinstance(raw, str) or not raw:
            raise ValueError("bits must be a nonempty binary string")
        if any(item not in {"0", "1"} for item in raw):
            raise ValueError("bits must be binary")
        bits = [int(item) for item in raw]
        output_mode = "string"
    else:
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)) or not raw:
            raise ValueError("bits must be a nonempty binary sequence")
        if any(not isinstance(item, int) or isinstance(item, bool) or item not in {0, 1} for item in raw):
            raise ValueError("bits must be binary integers")
        bits = list(raw)
        output_mode = "tuple" if isinstance(raw, tuple) else "list"
    if len(bits) > context.limits.max_state_count:
        raise BudgetExceeded("bit count exceeds configured bound")

    steps = value[data["steps_field"]]
    if not isinstance(steps, int) or isinstance(steps, bool):
        raise TypeError("step count must be an integer")
    if steps < 0:
        raise ValueError("step count must be nonnegative")
    if steps > context.limits.max_steps:
        raise BudgetExceeded("step count exceeds configured bound")

    rule = data["rule"]
    current = bits
    for _ in range(steps):
        context.tick()
        changed: list[int] = []
        for index in range(len(current)):
            context.tick()
            neighborhood = (
                (current[index - 1] << 2)
                | (current[index] << 1)
                | current[(index + 1) % len(current)]
            )
            changed.append((rule >> neighborhood) & 1)
        current = changed

    if output_mode == "string":
        return "".join(str(item) for item in current)
    if output_mode == "tuple":
        return tuple(current)
    return current



def _cyclic_skip_step(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> Any:
    cycle = value[data["cycle_field"]]
    if not isinstance(cycle, Sequence) or isinstance(cycle, (str, bytes, bytearray)):
        raise TypeError("cycle must be a sequence")
    if not cycle:
        raise ValueError("cycle must not be empty")
    if len(cycle) > context.limits.max_state_count:
        raise BudgetExceeded("cycle length exceeds configured bound")

    steps = value[data["steps_field"]]
    if not isinstance(steps, int) or isinstance(steps, bool):
        raise TypeError("step count must be an integer")
    if steps < 0:
        raise ValueError("step count must be nonnegative")
    if steps > context.limits.max_steps:
        raise BudgetExceeded("step count exceeds configured bound")

    order: list[bytes] = []
    values: dict[bytes, Any] = {}
    for item in cycle:
        context.tick()
        key = _canonical_bytes(item)
        if key in values:
            raise ValueError("duplicate cycle value")
        order.append(key)
        values[key] = deepcopy(item)

    start_key = _canonical_bytes(value[data["start_field"]])
    if start_key not in values:
        raise ValueError("start is not in cycle")

    blocked = value[data["blocked_field"]]
    if not isinstance(blocked, Sequence) or isinstance(blocked, (str, bytes, bytearray)):
        raise TypeError("blocked must be a sequence")
    if len(blocked) > context.limits.max_state_count:
        raise BudgetExceeded("blocked count exceeds configured bound")
    blocked_keys: set[bytes] = set()
    for item in blocked:
        context.tick()
        key = _canonical_bytes(item)
        if key not in values:
            raise ValueError("blocked value is not in cycle")
        blocked_keys.add(key)

    if steps > 0 and len(blocked_keys) == len(order):
        raise ValueError("cycle has no allowed cycle value")

    index = order.index(start_key)
    for _ in range(steps):
        while True:
            context.tick()
            index = (index + 1) % len(order)
            if order[index] not in blocked_keys:
                break
    return deepcopy(values[order[index]])

def _resource_makespan(data: Mapping[str, Any], value: Mapping[str, Any], context: EvaluationContext) -> int:
    jobs = list(value[data["jobs_field"]])
    if len(jobs) > context.limits.max_schedule_jobs:
        raise BudgetExceeded("job count exceeds configured bound")
    id_field = data["id_field"]
    duration_field = data["duration_field"]
    resource_field = data["resource_field"]
    ids = [job[id_field] for job in jobs]
    by_id = {job[id_field]: job for job in jobs}
    resources = sorted({job[resource_field] for job in jobs}, key=str)
    grouped = {resource: [job[id_field] for job in jobs if job[resource_field] == resource] for resource in resources}
    base_edges = [tuple(edge) for edge in value[data["precedence_field"]]]
    best: int | None = None
    order_sets = [tuple(itertools.permutations(grouped[resource])) for resource in resources]
    for selected in itertools.product(*order_sets):
        context.tick()
        edges = list(base_edges)
        for order in selected:
            edges.extend(zip(order, order[1:]))
        outgoing = {item: [] for item in ids}
        incoming = {item: [] for item in ids}
        indegree = {item: 0 for item in ids}
        for left, right in edges:
            if right not in outgoing[left]:
                outgoing[left].append(right)
                incoming[right].append(left)
                indegree[right] += 1
        queue = deque(sorted((item for item in ids if indegree[item] == 0), key=str))
        order: list[Any] = []
        while queue:
            item = queue.popleft()
            order.append(item)
            for nxt in sorted(outgoing[item], key=str):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(ids):
            continue
        finish: dict[Any, int] = {}
        for item in order:
            start = max((finish[parent] for parent in incoming[item]), default=0)
            finish[item] = start + int(by_id[item][duration_field])
        completion = max(finish.values(), default=0)
        best = completion if best is None else min(best, completion)
    if best is None:
        raise ValueError("no feasible resource order")
    return best

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
    if kind == "state_fold":
        if not isinstance(data.get("state_field"), str) or not isinstance(data.get("actions_field"), str):
            raise ValueError("state_fold requires state and actions fields")
        transitions = data.get("transitions")
        if not isinstance(transitions, Sequence) or isinstance(transitions, (str, bytes, bytearray)) or not transitions:
            raise ValueError("state_fold requires transitions")
        seen: dict[bytes, Any] = {}
        for transition in transitions:
            if not isinstance(transition, Mapping) or set(transition) != {"state", "action", "next"}:
                raise ValueError("invalid state_fold transition")
            key = _canonical_bytes([transition["state"], transition["action"]])
            if key in seen and seen[key] != transition["next"]:
                raise ValueError("conflicting transition")
            seen[key] = transition["next"]
        if data.get("unknown", "error") not in {"error", "identity"}:
            raise ValueError("invalid state_fold unknown policy")


    if kind == "stack_rewrite":
        if not isinstance(data.get("sequence_field"), str):
            raise ValueError("stack_rewrite requires a sequence field")
        if data.get("token_mode") not in {"items", "characters", "words"}:
            raise ValueError("invalid stack_rewrite token mode")
        rules = data.get("rules")
        if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes, bytearray)) or not rules:
            raise ValueError("stack_rewrite requires rules")
        seen_rules: dict[bytes, Any] = {}
        for rule in rules:
            if not isinstance(rule, Mapping) or set(rule) != {"left", "right"}:
                raise ValueError("invalid stack_rewrite rule")
            left = rule["left"]
            right = rule["right"]
            if (
                not isinstance(left, Sequence)
                or isinstance(left, (str, bytes, bytearray))
                or not left
                or not isinstance(right, Sequence)
                or isinstance(right, (str, bytes, bytearray))
            ):
                raise ValueError("invalid stack_rewrite rule")
            if list(left) == list(right):
                raise ValueError("identity rewrite is not allowed")
            key = _canonical_bytes(list(left))
            if key in seen_rules and seen_rules[key] != list(right):
                raise ValueError("conflicting rewrite")
            seen_rules[key] = list(right)


    if kind == "weighted_vote_veto":
        required_fields = (
            "ballots_field",
            "choice_field",
            "weight_field",
            "support_field",
            "veto_field",
        )
        if any(not isinstance(data.get(name), str) for name in required_fields):
            raise ValueError("weighted_vote_veto requires ballot field names")
        if not isinstance(data.get("threshold"), Real) or isinstance(data.get("threshold"), bool):
            raise ValueError("weighted_vote_veto threshold must be numeric")
        if data.get("tie_policy") not in {"lexicographic", "first", "error"}:
            raise ValueError("invalid weighted vote tie policy")
        if "default" not in data:
            raise ValueError("weighted_vote_veto requires a default")

    if kind == "ray_first_hit":
        required_fields = (
            "origin_field",
            "direction_field",
            "objects_field",
            "id_field",
            "min_field",
            "max_field",
        )
        if any(not isinstance(data.get(name), str) for name in required_fields):
            raise ValueError("ray_first_hit requires field names")
        if data.get("tie_policy") not in {"lexicographic", "first", "error"}:
            raise ValueError("invalid ray first-hit tie policy")
        if "default" not in data:
            raise ValueError("ray_first_hit requires a default")

    if kind == "distinct_slot_match":
        required_fields = ("items_field", "id_field", "slots_field")
        if any(not isinstance(data.get(name), str) for name in required_fields):
            raise ValueError("distinct_slot_match requires field names")
        if "success" not in data or "failure" not in data:
            raise ValueError("distinct_slot_match requires output labels")
        if type(data["success"]) is type(data["failure"]) and data["success"] == data["failure"]:
            raise ValueError("distinct_slot_match labels must differ")

    if kind == "integer_span_cover":
        required_fields = (
            "span_start_field",
            "span_end_field",
            "intervals_field",
            "interval_start_field",
            "interval_end_field",
        )
        if any(not isinstance(data.get(name), str) for name in required_fields):
            raise ValueError("integer_span_cover requires field names")
        if data.get("mode") not in {"minimum_count", "feasible"}:
            raise ValueError("invalid integer span cover mode")
        if "failure" not in data:
            raise ValueError("integer_span_cover requires a failure value")
        if data["mode"] == "feasible":
            if "success" not in data:
                raise ValueError("feasible span cover requires a success value")
            if type(data["success"]) is type(data["failure"]) and data["success"] == data["failure"]:
                raise ValueError("span cover labels must differ")

    if kind == "circular_bit_step":
        if not isinstance(data.get("sequence_field"), str) or not isinstance(data.get("steps_field"), str):
            raise ValueError("circular_bit_step requires field names")
        if data.get("token_mode") not in {"characters", "integers"}:
            raise ValueError("invalid circular bit token mode")
        rule = data.get("rule")
        if not isinstance(rule, int) or isinstance(rule, bool) or not 0 <= rule <= 255:
            raise ValueError("circular bit rule must be an integer from zero through 255")

    if kind == "cyclic_skip_step":
        required_fields = ("cycle_field", "start_field", "steps_field", "blocked_field")
        if any(not isinstance(data.get(name), str) for name in required_fields):
            raise ValueError("cyclic_skip_step requires field names")

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
    if kind == "modular_symbol":
        if not isinstance(value, Mapping):
            raise TypeError("symbol input must be a mapping")
        cycle = list(data["cycle"])
        modulus = int(data.get("modulus", len(cycle)))
        total = 0
        for term in data["terms"]:
            observed = value[term["field"]]
            number = cycle.index(observed) if term.get("mode") == "cycle" else int(observed)
            total += int(term.get("coefficient", 1)) * number
        return cycle[total % modulus]
    if kind == "priority_rules":
        if not isinstance(value, Mapping):
            raise TypeError("rule input must be a mapping")
        for rule in data["rules"]:
            if _condition_matches(rule["condition"], value):
                return rule["value"]
        return data["default"]
    if kind == "grid_pattern_count":
        if not isinstance(value, Mapping):
            raise TypeError("grid input must be a mapping")
        return _grid_count(data, value)
    if kind == "resource_makespan":
        if not isinstance(value, Mapping):
            raise TypeError("resource input must be a mapping")
        return _resource_makespan(data, value, context)
    if kind == "state_fold":
        if not isinstance(value, Mapping):
            raise TypeError("state-fold input must be a mapping")
        return _state_fold(data, value, context)
    if kind == "stack_rewrite":
        if not isinstance(value, Mapping):
            raise TypeError("stack-rewrite input must be a mapping")
        return _stack_rewrite(data, value, context)
    if kind == "weighted_vote_veto":
        if not isinstance(value, Mapping):
            raise TypeError("weighted-vote input must be a mapping")
        return _weighted_vote_veto(data, value, context)
    if kind == "ray_first_hit":
        if not isinstance(value, Mapping):
            raise TypeError("ray input must be a mapping")
        return _ray_first_hit(data, value, context)
    if kind == "distinct_slot_match":
        if not isinstance(value, Mapping):
            raise TypeError("matching input must be a mapping")
        return _distinct_slot_match(data, value, context)
    if kind == "integer_span_cover":
        if not isinstance(value, Mapping):
            raise TypeError("span-cover input must be a mapping")
        return _integer_span_cover(data, value, context)
    if kind == "circular_bit_step":
        if not isinstance(value, Mapping):
            raise TypeError("circular-bit input must be a mapping")
        return _circular_bit_step(data, value, context)
    if kind == "cyclic_skip_step":
        if not isinstance(value, Mapping):
            raise TypeError("cyclic-skip input must be a mapping")
        return _cyclic_skip_step(data, value, context)
    raise ValueError(f"unsupported node kind: {kind}")
