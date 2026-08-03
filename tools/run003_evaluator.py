from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import deque
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SUITE_ID = "holonomy-v2-run-003"
PROTOCOL = "commit-predict-reveal-v2"
DEMO_BUDGETS = (3, 5, 10, 20) * 4


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def pack(
    family: str,
    level: int,
    instructions: str,
    demo_inputs: Sequence[Any],
    fn: Callable[[Any], Any],
    hidden_inputs: Sequence[Any],
) -> tuple[dict[str, Any], list[Any]]:
    task = {
        "task_id": family,
        "family": family,
        "level": level,
        "instructions": instructions,
        "demonstrations": [{"input": item, "output": fn(item)} for item in demo_inputs],
        "hidden_inputs": list(hidden_inputs),
    }
    return task, [fn(item) for item in hidden_inputs]


def path_length(value: Mapping[str, Any]) -> int | None:
    links: dict[str, list[str]] = {}
    for left, right in value["graph"]["edges"]:
        links.setdefault(left, []).append(right)
        links.setdefault(right, [])
    queue = deque([(value["start"], 0)])
    seen = {value["start"]}
    while queue:
        node, depth = queue.popleft()
        if node == value["goal"]:
            return depth
        for nxt in links.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, depth + 1))
    return None


def resource_plan(value: Mapping[str, Any], jobs_key: str, edges_key: str, time_key: str, unit_key: str) -> int:
    jobs = value[jobs_key]
    ids = [item["id"] for item in jobs]
    by_id = {item["id"]: item for item in jobs}
    units = sorted({item[unit_key] for item in jobs})
    grouped = {unit: [item["id"] for item in jobs if item[unit_key] == unit] for unit in units}
    best: int | None = None
    choices = [tuple(itertools.permutations(grouped[unit])) for unit in units]
    for picked in itertools.product(*choices):
        edges = [tuple(item) for item in value[edges_key]]
        for order in picked:
            edges.extend(zip(order, order[1:]))
        outgoing = {item: [] for item in ids}
        incoming = {item: [] for item in ids}
        degree = {item: 0 for item in ids}
        for left, right in edges:
            if right not in outgoing[left]:
                outgoing[left].append(right)
                incoming[right].append(left)
                degree[right] += 1
        queue = deque(sorted(item for item in ids if degree[item] == 0))
        ordered: list[str] = []
        while queue:
            item = queue.popleft()
            ordered.append(item)
            for nxt in sorted(outgoing[item]):
                degree[nxt] -= 1
                if degree[nxt] == 0:
                    queue.append(nxt)
        if len(ordered) != len(ids):
            continue
        finish: dict[str, int] = {}
        for item in ordered:
            start = max((finish[parent] for parent in incoming[item]), default=0)
            finish[item] = start + by_id[item][time_key]
        value_now = max(finish.values(), default=0)
        best = value_now if best is None else min(best, value_now)
    if best is None:
        raise ValueError("no feasible order")
    return best


def build_affine(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    a = rng.choice([-9, -6, -4, 3, 5, 8])
    b = rng.randint(-37, 37)
    fn = lambda x: a * x + b
    demos = [rng.randint(-40, 40) for _ in range(budget)]
    hidden = [rng.randint(-500, 500) for _ in range(50)]
    return pack("affine-fresh-v3", 1, f"Return {a}*n+{b}.", demos, fn, hidden)


def build_token(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    count = max(3, min(7, budget))
    tokens = [f"cue{rng.randrange(10_000)}x{i}" for i in range(count)]
    labels = [f"class{rng.randrange(1000)}-{i}" for i in range(count)]
    mapping = dict(zip(tokens, labels))
    fn = lambda value: next(label for token, label in mapping.items() if token in value.split())
    text = " ".join(f"The token {token} means {label}." for token, label in mapping.items())
    demos = [f"noise {token} data" for token in tokens]
    while len(demos) < budget:
        token = rng.choice(tokens)
        demos.append(f"prefix {token} suffix")
    hidden = [f"item {rng.choice(tokens)} extra{rng.randrange(100)}" for _ in range(50)]
    return pack("token-map-fresh-v3", 2, text, demos[:budget], fn, hidden)


def build_modular(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    size = rng.choice([5, 6, 7])
    cycle = [f"sym{rng.randrange(10_000)}-{i}" for i in range(size)]
    factor = rng.choice([2, 3, 4])
    index = {item: i for i, item in enumerate(cycle)}
    fn = lambda value: cycle[(index[value["left"]] + factor * index[value["right"]] + value["phase"]) % size]
    make = lambda: {"left": rng.choice(cycle), "right": rng.choice(cycle), "phase": rng.randrange(size)}
    text = (
        f"Symbols cycle in this order: {', '.join(cycle)}. Convert left and right to their zero-based cycle positions. "
        f"Add left + {factor}*right + phase, reduce modulo {size}, and return the symbol at that position."
    )
    return pack("modular-symbol-fresh-v3", 2, text, [make() for _ in range(budget)], fn, [make() for _ in range(50)])


def build_order_project(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    key = rng.choice(["weight", "rank", "priority"])
    out = rng.choice(["glyph", "tag", "code"])
    make = lambda prefix: [{out: f"{prefix}-{i}", key: rng.randint(-50, 50)} for i in range(rng.randint(5, 9))]
    fn = lambda rows: [item[out] for item in sorted(rows, key=lambda item: item[key])]
    text = f"Order entries by increasing {key}, then return only the {out} values."
    return pack("order-project-fresh-v3", 2, text, [make(f"d{i}") for i in range(budget)], fn, [make(f"h{i}") for i in range(50)])


def build_filter_sum(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    gate = rng.choice(["charge", "score", "gate"])
    out = rng.choice(["payload", "value", "credit"])
    threshold = rng.randint(4, 18)
    make = lambda: [{gate: rng.randint(0, 30), out: rng.randint(-25, 60)} for _ in range(rng.randint(6, 10))]
    fn = lambda rows: sum(item[out] for item in rows if item[gate] >= threshold)
    text = f"Among entries whose {gate} is at least {threshold}, sum the {out} values."
    return pack("filter-sum-fresh-v3", 2, text, [make() for _ in range(budget)], fn, [make() for _ in range(50)])


def build_graph_label(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    nodes = [f"node{rng.randrange(10_000)}-{i}" for i in range(8)]
    edges = [[nodes[i], nodes[i + 1]] for i in range(7)] + [[nodes[0], nodes[4]], [nodes[2], nodes[6]]]
    yes, no = f"OPEN{rng.randrange(1000)}", f"CLOSED{rng.randrange(1000)}"
    make = lambda: {"graph": {"edges": edges, "directed": True}, "start": rng.choice(nodes), "goal": rng.choice(nodes)}
    fn = lambda value: yes if path_length(value) is not None else no
    text = f"Return {yes} when a directed route exists and {no} otherwise."
    demos = [make() for _ in range(budget)]
    if budget >= 2:
        demos[0] = {"graph": {"edges": edges, "directed": True}, "start": nodes[0], "goal": nodes[-1]}
        demos[1] = {"graph": {"edges": edges, "directed": True}, "start": nodes[-1], "goal": nodes[0]}
    return pack("graph-label-fresh-v3", 3, text, demos, fn, [make() for _ in range(50)])


def build_priority(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    allow, deny = f"ALLOW{rng.randrange(1000)}", f"DENY{rng.randrange(1000)}"
    fields = ["storm", "rescue", "charter", "witness", "licensed", "copper", "ivory"]
    def fn(value: Mapping[str, Any]) -> str:
        if value["storm"] and not value["rescue"]:
            return deny
        if value["charter"] and value["witness"]:
            return allow
        if value["licensed"] and (value["copper"] or value["ivory"]):
            return allow
        return deny
    make = lambda: {field: bool(rng.randrange(2)) for field in fields}
    text = (
        "Apply these rules in priority order. During a storm, deny unless rescue is true. "
        "Otherwise, charter together with witness allows. Otherwise, licensed together with either copper or ivory allows. "
        f"All remaining cases deny. Return {allow} or {deny}."
    )
    demos = [make() for _ in range(budget)]
    return pack("priority-rules-fresh-v3", 3, text, demos, fn, [make() for _ in range(50)])


def build_resource(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    jobs_key = rng.choice(["jobs", "tasks"])
    edges_key = rng.choice(["precedence", "before"])
    time_key = rng.choice(["duration", "time"])
    unit_key = rng.choice(["machine", "resource"])
    def make(prefix: str) -> dict[str, Any]:
        jobs = [{"id": f"{prefix}-{i}", time_key: rng.randint(1, 9), unit_key: "M1" if i % 2 == 0 else "M2"} for i in range(4)]
        return {jobs_key: jobs, edges_key: [[jobs[0]["id"], jobs[2]["id"]], [jobs[1]["id"], jobs[3]["id"]]]}
    fn = lambda value: resource_plan(value, jobs_key, edges_key, time_key, unit_key)
    text = (
        f"Each job has a {time_key} and requires one named {unit_key}. A {unit_key} handles at most one job at a time; "
        "jobs are non-preemptive; every precedence pair must be respected. Return the minimum possible completion time for all jobs."
    )
    return pack("resource-plan-fresh-v3", 3, text, [make(f"d{i}") for i in range(budget)], fn, [make(f"h{i}") for i in range(50)])


def build_state_fold(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    states = [f"q{i}" for i in range(5)]
    actions = ["lift", "turn", "drop"]
    offsets = {actions[0]: 1, actions[1]: 2, actions[2]: -1}
    transitions = {(state, action): states[(i + offsets[action]) % len(states)] for i, state in enumerate(states) for action in actions}
    def fn(value: Mapping[str, Any]) -> str:
        state = value["state"]
        for action in value["actions"]:
            state = transitions[(state, action)]
        return state
    make = lambda: {"state": rng.choice(states), "actions": [rng.choice(actions) for _ in range(rng.randrange(0, 9))]}
    clauses = "; ".join(f"{state} + {action} -> {nxt}" for (state, action), nxt in transitions.items())
    text = f"Apply this transition table in action order: {clauses}. Return the final state."
    return pack("state-action-fold-v3", 4, text, [make() for _ in range(budget)], fn, [make() for _ in range(50)])


def rewrite_words(tokens: Sequence[str]) -> list[str]:
    stack: list[str] = []
    rules = [(["a", "b"], ["c"]), (["c", "c"], [])]
    for token in tokens:
        stack.append(token)
        changed = True
        while changed:
            changed = False
            for left, right in rules:
                if len(stack) >= len(left) and stack[-len(left):] == left:
                    stack[-len(left):] = right
                    changed = True
                    break
    return stack


def build_stack_rewrite(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    def make() -> dict[str, str]:
        tokens = [rng.choice(["a", "b", "c"]) for _ in range(rng.randrange(2, 15))]
        return {"tokens": " ".join(tokens)}
    fn = lambda value: " ".join(rewrite_words(value["tokens"].split()))
    text = "Use stack rewrite rules: a b -> c; c c -> empty. Return the final stack as words."
    return pack("stack-rewrite-v3", 4, text, [make() for _ in range(budget)], fn, [make() for _ in range(50)])


def weighted_target(value: Mapping[str, Any]) -> str:
    scores: dict[str, int] = {}
    vetoed: set[str] = set()
    for ballot in value["ballots"]:
        option = ballot["option"]
        scores.setdefault(option, 0)
        scores[option] += ballot["weight"] * (1 if ballot["support"] else -1)
        if ballot["veto"]:
            vetoed.add(option)
    eligible = [item for item, score in scores.items() if item not in vetoed and score >= 0]
    if not eligible:
        return "NONE"
    best = max(scores[item] for item in eligible)
    return min(item for item in eligible if scores[item] == best)


def build_weighted(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    options = [f"OPT{i}" for i in range(4)]
    def make() -> dict[str, Any]:
        ballots = []
        for _ in range(rng.randint(4, 12)):
            ballots.append({
                "option": rng.choice(options),
                "weight": rng.randint(0, 7),
                "support": bool(rng.randrange(2)),
                "veto": rng.random() < 0.12,
            })
        return {"ballots": ballots}
    text = (
        "Use weighted vote with veto. Each ballot has option, weight, support, and veto. Support adds its weight and opposition "
        "subtracts its weight. Any veto eliminates that option. Return the non-vetoed option with greatest score. Minimum score 0; "
        "break ties lexicographically; otherwise return NONE."
    )
    return pack("weighted-vote-veto-v3", 4, text, [make() for _ in range(budget)], weighted_target, [make() for _ in range(50)])


def ray_target(value: Mapping[str, Any]) -> str:
    ox, oy = value["origin"]
    dx, dy = value["direction"]
    best: tuple[float, str] | None = None
    for obj in value["objects"]:
        entered = 0.0
        exited = math.inf
        hit = True
        for pos, delta, low, high in zip((ox, oy), (dx, dy), obj["min"], obj["max"]):
            if delta == 0:
                if not low <= pos <= high:
                    hit = False
                    break
                continue
            a, b = (low - pos) / delta, (high - pos) / delta
            entered = max(entered, min(a, b))
            exited = min(exited, max(a, b))
            if exited < entered:
                hit = False
                break
        if not hit or exited < 0:
            continue
        candidate = (max(entered, 0.0), obj["id"])
        if best is None or candidate < best:
            best = candidate
    return "NONE" if best is None else best[1]


def build_ray(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    directions = ([1, 0], [0, 1], [-1, 0], [0, -1])
    def make(prefix: str) -> dict[str, Any]:
        direction = list(rng.choice(directions))
        objects = []
        for i in range(rng.randint(2, 6)):
            x = rng.randint(-9, 9)
            y = rng.randint(-9, 9)
            objects.append({"id": f"{prefix}-{i}", "min": [x, y], "max": [x + rng.randint(1, 3), y + rng.randint(1, 3)]})
        return {"origin": [0, 0], "direction": direction, "objects": objects}
    text = (
        "Cast a ray from origin in direction. Each object has id, min, and max coordinates for an axis-aligned box. "
        "Return the id of the first box hit. Break ties lexicographically; otherwise return NONE."
    )
    demos = [make(f"d{i}") for i in range(budget)]
    if demos:
        demos[0] = {"origin": [0, 0], "direction": [1, 0], "objects": [{"id": "near", "min": [2, -1], "max": [3, 1]}, {"id": "far", "min": [5, -1], "max": [6, 1]}]}
    if len(demos) > 1:
        demos[1] = {"origin": [0, 0], "direction": [1, 0], "objects": [{"id": "miss", "min": [2, 3], "max": [3, 4]}]}
    return pack("ray-first-hit-v3", 4, text, demos, ray_target, [make(f"h{i}") for i in range(50)])


def has_matching(value: Mapping[str, Any]) -> str:
    adjacency = {item["id"]: list(item["slots"]) for item in value["items"]}
    owner: dict[str, str] = {}
    def place(item: str, seen: set[str]) -> bool:
        for slot in adjacency[item]:
            if slot in seen:
                continue
            seen.add(slot)
            if slot not in owner or place(owner[slot], seen):
                owner[slot] = item
                return True
        return False
    return "YES" if all(place(item, set()) for item in sorted(adjacency)) else "NO"


def build_matching(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    def make(force: str | None = None) -> dict[str, Any]:
        count = rng.randint(3, 7)
        slots = [f"S{i}" for i in range(count)]
        items = []
        for i in range(count):
            choices = rng.sample(slots, rng.randint(1, min(4, count)))
            items.append({"id": f"I{i}", "slots": choices})
        if force == "yes":
            for i, item in enumerate(items):
                item["slots"] = list(dict.fromkeys([slots[i], *item["slots"]]))
        if force == "no":
            for item in items:
                item["slots"] = [slots[0]]
        return {"items": items}
    demos = [make() for _ in range(budget)]
    if demos:
        demos[0] = make("yes")
    if len(demos) > 1:
        demos[1] = make("no")
    text = "Assign every item to one distinct slot from its slots list. Return YES if a complete distinct matching exists; otherwise return NO."
    return pack("distinct-slot-match-v3", 4, text, demos, has_matching, [make() for _ in range(50)])


def span_target(value: Mapping[str, Any]) -> int:
    position = value["start"]
    end = value["end"]
    intervals = sorted((item["start"], item["end"]) for item in value["intervals"])
    index = count = 0
    while position <= end:
        farthest = position - 1
        while index < len(intervals) and intervals[index][0] <= position:
            farthest = max(farthest, intervals[index][1])
            index += 1
        if farthest < position:
            return -1
        count += 1
        position = farthest + 1
    return count


def build_span(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    def make(force: str | None = None) -> dict[str, Any]:
        start = rng.randint(-20, 20)
        end = start + rng.randint(4, 18)
        intervals = []
        for _ in range(rng.randint(3, 10)):
            left = rng.randint(start - 3, end + 2)
            intervals.append({"start": left, "end": left + rng.randint(0, 7)})
        if force == "yes":
            mid = (start + end) // 2
            intervals.extend([{"start": start, "end": mid}, {"start": mid + 1, "end": end}])
        if force == "no":
            intervals = [{"start": start, "end": start + 1}, {"start": start + 3, "end": end}]
        return {"start": start, "end": end, "intervals": intervals}
    demos = [make() for _ in range(budget)]
    if demos:
        demos[0] = make("yes")
    if len(demos) > 1:
        demos[1] = make("no")
    text = "Cover every integer from start through end using the minimum number of intervals. Intervals include both endpoints. Return -1 if the span cannot be covered."
    return pack("integer-span-cover-v3", 4, text, demos, span_target, [make() for _ in range(50)])


def eca_target(value: Mapping[str, Any], rule: int) -> str:
    current = [int(item) for item in value["bits"]]
    for _ in range(value["steps"]):
        current = [
            (rule >> ((current[i - 1] << 2) | (current[i] << 1) | current[(i + 1) % len(current)])) & 1
            for i in range(len(current))
        ]
    return "".join(str(item) for item in current)


def build_circular(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    rule = rng.choice([30, 45, 54, 60, 73, 90, 105, 110, 150, 182])
    make = lambda: {"bits": "".join(str(rng.randrange(2)) for _ in range(rng.randint(5, 16))), "steps": rng.randint(0, 8)}
    fn = lambda value: eca_target(value, rule)
    text = f"Apply elementary cellular automaton rule {rule} to bits on a circular ring for the given number of steps. Return the resulting bits."
    return pack("circular-bit-step-v3", 4, text, [make() for _ in range(budget)], fn, [make() for _ in range(50)])


def cyclic_target(value: Mapping[str, Any]) -> Any:
    cycle = value["cycle"]
    blocked = set(value["blocked"])
    index = cycle.index(value["start"])
    for _ in range(value["steps"]):
        while True:
            index = (index + 1) % len(cycle)
            if cycle[index] not in blocked:
                break
    return cycle[index]


def build_cyclic(rng: random.Random, budget: int) -> tuple[dict[str, Any], list[Any]]:
    cycle = [f"day-{rng.randrange(10_000)}-{i}" for i in range(7)]
    def make() -> dict[str, Any]:
        blocked_count = rng.randint(0, 4)
        blocked = rng.sample(cycle, blocked_count)
        return {"cycle": list(cycle), "start": rng.choice(cycle), "steps": rng.randint(0, 15), "blocked": blocked}
    text = "Move forward around cycle from start by the given number of allowed steps. Skip every value listed in blocked and wrap around the cycle."
    return pack("blocked-day-cycle-v3", 4, text, [make() for _ in range(budget)], cyclic_target, [make() for _ in range(50)])


BUILDERS = (
    build_affine,
    build_token,
    build_modular,
    build_order_project,
    build_filter_sum,
    build_graph_label,
    build_priority,
    build_resource,
    build_state_fold,
    build_stack_rewrite,
    build_weighted,
    build_ray,
    build_matching,
    build_span,
    build_circular,
    build_cyclic,
)


def build_suite(seed_hex: str) -> tuple[list[dict[str, Any]], dict[str, list[Any]]]:
    rng = random.Random(int(seed_hex, 16))
    tasks: list[dict[str, Any]] = []
    targets: dict[str, list[Any]] = {}
    for builder, budget in zip(BUILDERS, DEMO_BUDGETS):
        task, task_targets = builder(rng, budget)
        tasks.append(task)
        targets[task["task_id"]] = task_targets
    return tasks, targets


def cmd_build(args: argparse.Namespace) -> None:
    output = Path(args.output)
    tasks, targets = build_suite(args.seed_hex)
    public = {
        "suite_id": SUITE_ID,
        "frozen_head": args.frozen_head,
        "created_at": args.created_at,
        "tasks": tasks,
    }
    scoring = {
        "headline_level": 4,
        "abstention_counts_incorrect": True,
        "equality": "json-structural",
        "first_attempt": "attempt-0001",
    }
    private = {
        "suite_id": SUITE_ID,
        "frozen_head": args.frozen_head,
        "created_at": args.created_at,
        "seed_hex": args.seed_hex,
        "nonce": args.nonce,
        "targets": targets,
        "scoring": scoring,
        "evaluator_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    public_digest = digest(public)
    private_digest = digest(private)
    scoring_digest = digest(scoring)
    commitment_body = {
        "suite_id": SUITE_ID,
        "protocol": PROTOCOL,
        "frozen_head": args.frozen_head,
        "created_at": args.created_at,
        "public_digest": public_digest,
        "private_digest": private_digest,
        "scoring_digest": scoring_digest,
        "nonce_sha256": hashlib.sha256(args.nonce.encode()).hexdigest(),
        "evaluator_source_sha256": private["evaluator_source_sha256"],
    }
    commitment = {**commitment_body, "commitment_digest": digest(commitment_body)}
    public_index = {
        "suite_id": SUITE_ID,
        "frozen_head": args.frozen_head,
        "commitment_digest": commitment["commitment_digest"],
        "public_digest": public_digest,
        "tasks": len(tasks),
        "hidden_rows": sum(len(task["hidden_inputs"]) for task in tasks),
        "new_system_families": sum(task["level"] == 4 for task in tasks),
        "demonstration_budgets": list(DEMO_BUDGETS),
    }
    write_json(output / "COMMITMENT.json", commitment)
    write_json(output / "PUBLIC_CHALLENGE.json", public)
    write_json(output / "PRIVATE_REVEAL.json", private)
    write_json(output / "PUBLIC_INDEX.json", public_index)


def cmd_submit(args: argparse.Namespace) -> None:
    from universal_core.holonomy_v2.blind_adapter import run_public_task_v2
    from universal_core.holonomy_v2.engine import HolonomyEngine
    from universal_core.holonomy_v2.types import SearchConfig

    public = read_json(Path(args.public))
    commitment = read_json(Path(args.commitment))
    if digest(public) != commitment["public_digest"]:
        raise ValueError("public digest mismatch")
    if args.frozen_head != commitment["frozen_head"] or public["frozen_head"] != args.frozen_head:
        raise ValueError("frozen head mismatch")
    engine = HolonomyEngine(SearchConfig(tier="D"))
    task_submissions = [run_public_task_v2(task, engine) for task in public["tasks"]]
    body = {
        "suite_id": SUITE_ID,
        "attempt": "attempt-0001",
        "tier": "D",
        "created_at": args.created_at,
        "frozen_head": args.frozen_head,
        "public_digest": commitment["public_digest"],
        "task_submissions": task_submissions,
    }
    submission = {**body, "submission_digest": digest(body)}
    output = Path(args.output)
    write_json(output / "SUBMISSION.json", submission)
    write_json(output / "SUBMISSION_DIGEST.json", {
        "suite_id": SUITE_ID,
        "attempt": "attempt-0001",
        "tier": "D",
        "created_at": args.created_at,
        "frozen_head": args.frozen_head,
        "public_digest": commitment["public_digest"],
        "submission_digest": submission["submission_digest"],
        "tasks": len(task_submissions),
        "predictions": sum(len(item["predictions"]) for item in task_submissions),
    })


def wilson(correct: int, total: int) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - spread), min(1.0, center + spread)]


def empty_metrics() -> dict[str, int]:
    return {"rows": 0, "attempted": 0, "correct": 0, "incorrect": 0, "abstained": 0, "failures": 0}


def finalize_metrics(metrics: Mapping[str, int], with_wilson: bool = False) -> dict[str, Any]:
    rows = metrics["rows"]
    attempted = metrics["attempted"]
    correct = metrics["correct"]
    result: dict[str, Any] = dict(metrics)
    result["raw_accuracy"] = 0.0 if rows == 0 else correct / rows
    result["coverage"] = 0.0 if rows == 0 else attempted / rows
    result["attempted_accuracy"] = 0.0 if attempted == 0 else correct / attempted
    if with_wilson:
        result["wilson_95"] = wilson(correct, rows)
    return result


def score_row(metrics: dict[str, int], prediction: Mapping[str, Any], target: Any) -> None:
    metrics["rows"] += 1
    status = prediction.get("status")
    if status == "ACCEPTED":
        metrics["attempted"] += 1
        if prediction.get("prediction") == target:
            metrics["correct"] += 1
        else:
            metrics["incorrect"] += 1
    elif status == "EXECUTION_FAILED":
        metrics["attempted"] += 1
        metrics["incorrect"] += 1
        metrics["failures"] += 1
    else:
        metrics["abstained"] += 1


def cmd_score(args: argparse.Namespace) -> None:
    commitment = read_json(Path(args.commitment))
    public = read_json(Path(args.public))
    private = read_json(Path(args.private))
    submission = read_json(Path(args.submission))
    checks = {
        "commitment": digest({key: commitment[key] for key in commitment if key != "commitment_digest"}) == commitment["commitment_digest"],
        "public": digest(public) == commitment["public_digest"],
        "private": digest(private) == commitment["private_digest"],
        "scoring": digest(private["scoring"]) == commitment["scoring_digest"],
        "nonce": hashlib.sha256(private["nonce"].encode()).hexdigest() == commitment["nonce_sha256"],
        "frozen_head": submission["frozen_head"] == commitment["frozen_head"] == public["frozen_head"] == private["frozen_head"],
        "submission": digest({key: submission[key] for key in submission if key != "submission_digest"}) == submission["submission_digest"],
        "first_attempt": submission["attempt"] == "attempt-0001",
    }
    if not all(checks.values()):
        raise ValueError(f"integrity check failed: {checks}")
    tasks = {task["task_id"]: task for task in public["tasks"]}
    submissions = {item["task_id"]: item for item in submission["task_submissions"]}
    if set(tasks) != set(submissions) or set(tasks) != set(private["targets"]):
        raise ValueError("task set mismatch")

    by_family: dict[str, dict[str, int]] = {}
    by_level_raw: dict[str, dict[str, int]] = {}
    overall = empty_metrics()
    for task_id, task in tasks.items():
        family = task["family"]
        level = str(task["level"])
        family_metrics = by_family.setdefault(family, empty_metrics())
        level_metrics = by_level_raw.setdefault(level, empty_metrics())
        predictions = submissions[task_id]["predictions"]
        targets = private["targets"][task_id]
        if len(predictions) != len(targets):
            raise ValueError("prediction count mismatch")
        for prediction, target in zip(predictions, targets):
            score_row(family_metrics, prediction, target)
            score_row(level_metrics, prediction, target)
            score_row(overall, prediction, target)

    by_level = {key: finalize_metrics(value, with_wilson=True) for key, value in sorted(by_level_raw.items())}
    headline = by_level.get("4", finalize_metrics(empty_metrics(), with_wilson=True))
    report_body = {
        "suite_id": SUITE_ID,
        "generated_at": args.created_at,
        "frozen_head": commitment["frozen_head"],
        "commitment_digest": commitment["commitment_digest"],
        "public_digest": commitment["public_digest"],
        "private_digest": commitment["private_digest"],
        "submission_digest": submission["submission_digest"],
        "checks": checks,
        "headline": headline,
        "overall": finalize_metrics(overall, with_wilson=True),
        "by_level": by_level,
        "by_family": {key: finalize_metrics(value) for key, value in sorted(by_family.items())},
        "full_report_in_evidence": True,
    }
    report = {**report_body, "report_digest": digest(report_body)}
    output = Path(args.output)
    write_json(output / "SCORE_REPORT.json", report)
    write_json(output / "REVEAL_INDEX.json", {
        "suite_id": SUITE_ID,
        "revealed_at": args.created_at,
        "private_digest": commitment["private_digest"],
        "scoring_digest": commitment["scoring_digest"],
        "nonce": private["nonce"],
        "reveal_file_sha256": hashlib.sha256(Path(args.private).read_bytes()).hexdigest(),
        "full_reveal_in_evidence": True,
    })


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output", required=True)
    build.add_argument("--frozen-head", required=True)
    build.add_argument("--created-at", required=True)
    build.add_argument("--seed-hex", required=True)
    build.add_argument("--nonce", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--public", required=True)
    submit.add_argument("--commitment", required=True)
    submit.add_argument("--output", required=True)
    submit.add_argument("--frozen-head", required=True)
    submit.add_argument("--created-at", required=True)
    score = sub.add_parser("score")
    score.add_argument("--public", required=True)
    score.add_argument("--private", required=True)
    score.add_argument("--commitment", required=True)
    score.add_argument("--submission", required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--created-at", required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "build":
        cmd_build(args)
    elif args.command == "submit":
        cmd_submit(args)
    else:
        cmd_score(args)


if __name__ == "__main__":
    main()
