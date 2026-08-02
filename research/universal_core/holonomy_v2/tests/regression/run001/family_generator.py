from __future__ import annotations

import itertools
import random
from collections import deque
from typing import Any, Callable


def _pack(text: str, inputs: list[Any], fn: Callable[[Any], Any], hidden: list[Any]) -> dict[str, Any]:
    return {
        "task_id": "mutation",
        "instructions": text,
        "demonstrations": [{"input": item, "output": fn(item)} for item in inputs],
        "hidden_inputs": hidden,
        "targets": [fn(item) for item in hidden],
    }


def _path(value: dict[str, Any]) -> int | None:
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


def _plan(value: dict[str, Any], jobs_key: str, edges_key: str, time_key: str, unit_key: str) -> int:
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
        order: list[str] = []
        while queue:
            item = queue.popleft()
            order.append(item)
            for nxt in sorted(outgoing[item]):
                degree[nxt] -= 1
                if degree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(ids):
            continue
        finish: dict[str, int] = {}
        for item in order:
            start = max((finish[parent] for parent in incoming[item]), default=0)
            finish[item] = start + by_id[item][time_key]
        value_now = max(finish.values())
        best = value_now if best is None else min(best, value_now)
    if best is None:
        raise ValueError("no feasible order")
    return best


def _affine(rng: random.Random) -> dict[str, Any]:
    a, b = rng.choice([-5, -3, 2, 4, 7]), rng.randint(-20, 20)
    fn = lambda x: a * x + b
    return _pack(f"Return {a}*n+{b}.", [-3, 1, 6], fn, [rng.randint(-50, 50) for _ in range(10)])


def _graph(rng: random.Random, label: bool) -> dict[str, Any]:
    nodes = [f"v{rng.randrange(1000)}-{i}" for i in range(6)]
    edges = [[nodes[i], nodes[i + 1]] for i in range(5)] + [[nodes[0], nodes[3]]]
    make = lambda a, b: {"graph": {"edges": edges, "directed": True}, "start": nodes[a], "goal": nodes[b]}
    demos = [make(0, 5), make(1, 4), make(5, 0)]
    hidden = [make(rng.randrange(6), rng.randrange(6)) for _ in range(10)]
    if not label:
        return _pack("Return the directed shortest path length, or null when no route exists.", demos, _path, hidden)
    yes, no = f"OPEN{rng.randrange(100)}", f"CLOSED{rng.randrange(100)}"
    fn = lambda value: yes if _path(value) is not None else no
    return _pack(f"Return {yes} when a directed route exists and {no} otherwise.", demos, fn, hidden)


def _table(rng: random.Random, mode: int) -> dict[str, Any]:
    if mode == 0:
        key, out = rng.choice(["rank", "weight", "merit"]), rng.choice(["tag", "glyph", "name"])
        make = lambda p: [{out: f"{p}-{i}", key: rng.randint(-20, 20)} for i in range(6)]
        fn = lambda rows: sorted(rows, key=lambda item: item[key], reverse=True)
        text = f"Sort records by {key} descending and return the full records."
    elif mode == 1:
        key, out = rng.choice(["weight", "rank", "priority"]), rng.choice(["glyph", "tag", "code"])
        make = lambda p: [{out: f"{p}-{i}", key: rng.randint(-20, 20)} for i in range(6)]
        fn = lambda rows: [item[out] for item in sorted(rows, key=lambda item: item[key])]
        text = f"Order entries by increasing {key}, then return only the {out} values."
    elif mode == 2:
        key, threshold = rng.choice(["measure", "level", "amount"]), rng.randint(-5, 12)
        make = lambda p: [{"tag": f"{p}-{i}", key: rng.randint(-20, 25)} for i in range(7)]
        fn = lambda rows: sum(item[key] >= threshold for item in rows)
        text = f"Report how many entries have a {key} no less than {threshold}."
    else:
        gate, out, threshold = rng.choice(["charge", "score", "gate"]), rng.choice(["payload", "value", "credit"]), rng.randint(3, 15)
        make = lambda p: [{gate: rng.randint(0, 25), out: rng.randint(-15, 40)} for _ in range(7)]
        fn = lambda rows: sum(item[out] for item in rows if item[gate] >= threshold)
        text = f"Among entries whose {gate} is at least {threshold}, sum the {out} values."
    return _pack(text, [make(f"d{i}") for i in range(3)], fn, [make(f"h{i}") for i in range(10)])


def _token(rng: random.Random) -> dict[str, Any]:
    tokens = [f"cue{rng.randrange(1000)}{i}" for i in range(3)]
    labels = [f"class{i}" for i in range(3)]
    mapping = dict(zip(tokens, labels))
    fn = lambda value: next(label for token, label in mapping.items() if token in value.split())
    text = " ".join(f"The token {token} means {label}." for token, label in mapping.items())
    return _pack(text, [f"noise {token} data" for token in tokens], fn, [f"item {rng.choice(tokens)} extra" for _ in range(10)])


def _modular(rng: random.Random) -> dict[str, Any]:
    cycle = [f"s{rng.randrange(1000)}{i}" for i in range(5)]
    index = {item: i for i, item in enumerate(cycle)}
    fn = lambda value: cycle[(index[value["left"]] + 2 * index[value["right"]] + value["phase"]) % 5]
    make = lambda: {"left": rng.choice(cycle), "right": rng.choice(cycle), "phase": rng.randrange(5)}
    text = f"Symbols cycle in this order: {', '.join(cycle)}. Convert left and right to their zero-based cycle positions. Add left + 2*right + phase, reduce modulo 5, and return the symbol at that position."
    return _pack(text, [make() for _ in range(5)], fn, [make() for _ in range(10)])


def _priority(rng: random.Random) -> dict[str, Any]:
    allow, deny = f"ALLOW{rng.randrange(100)}", f"DENY{rng.randrange(100)}"
    fields = ["storm", "rescue", "charter", "witness", "licensed", "copper", "ivory"]
    def fn(value: dict[str, Any]) -> str:
        if value["storm"] and not value["rescue"]:
            return deny
        if value["charter"] and value["witness"]:
            return allow
        if value["licensed"] and (value["copper"] or value["ivory"]):
            return allow
        return deny
    make = lambda: {field: bool(rng.randrange(2)) for field in fields}
    text = f"Apply these rules in priority order. During a storm, deny unless rescue is true. Otherwise, charter together with witness allows. Otherwise, licensed together with either copper or ivory allows. All remaining cases deny. Return {allow} or {deny}."
    return _pack(text, [make() for _ in range(10)], fn, [make() for _ in range(10)])


def _grid(rng: random.Random) -> dict[str, Any]:
    size = rng.choice([4, 5])
    def fn(value: dict[str, Any]) -> int:
        board, player = value["board"], value["player"]
        other = "B" if player == "A" else "A"
        total = 0
        for row in range(size):
            for col in range(size):
                if board[row][col] != player:
                    continue
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    er, ec, mr, mc = row + 2 * dr, col + 2 * dc, row + dr, col + dc
                    total += int(0 <= er < size and 0 <= ec < size and board[mr][mc] == other and board[er][ec] == ".")
        return total
    make = lambda: {"board": ["".join(rng.choice([".", ".", "A", "B"]) for _ in range(size)) for _ in range(size)], "player": rng.choice(["A", "B"])}
    text = f"On the {size}x{size} board, a legal move jumps one of the player's pieces exactly two squares orthogonally over one adjacent opponent piece into an empty dot. Count all legal moves for the named player."
    return _pack(text, [make() for _ in range(5)], fn, [make() for _ in range(10)])


def _resource(rng: random.Random) -> dict[str, Any]:
    jobs_key, edges_key = rng.choice(["jobs", "tasks"]), rng.choice(["precedence", "before"])
    time_key, unit_key = rng.choice(["duration", "time"]), rng.choice(["machine", "resource"])
    def make(prefix: str) -> dict[str, Any]:
        jobs = [{"id": f"{prefix}-{i}", time_key: rng.randint(1, 7), unit_key: "M1" if i % 2 == 0 else "M2"} for i in range(4)]
        return {jobs_key: jobs, edges_key: [[jobs[0]["id"], jobs[2]["id"]], [jobs[1]["id"], jobs[3]["id"]]]}
    fn = lambda value: _plan(value, jobs_key, edges_key, time_key, unit_key)
    text = f"Each job has a {time_key} and requires one named {unit_key}. A {unit_key} handles at most one job at a time; jobs are non-preemptive; every precedence pair must be respected. Return the minimum possible completion time for all jobs."
    return _pack(text, [make(f"d{i}") for i in range(3)], fn, [make(f"h{i}") for i in range(10)])


_BUILDERS = (_affine, lambda r: _graph(r, False), lambda r: _table(r, 0), lambda r: _table(r, 2), _token, lambda r: _table(r, 3), lambda r: _table(r, 1), lambda r: _graph(r, True), _modular, _priority, _grid, _resource)


def generate_mutation(seed: int) -> dict[str, Any]:
    return _BUILDERS[seed % len(_BUILDERS)](random.Random(seed))
