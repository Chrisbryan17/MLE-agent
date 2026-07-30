from __future__ import annotations

from random import Random
from typing import Any

from universal_core.contracts import Demonstration, OutputSchema, TaskPackage


def _check_count(demonstration_count: int) -> None:
    if not 3 <= demonstration_count <= 20:
        raise ValueError("demonstration_count must be between 3 and 20")


def _metadata(family: str, seed: int, task_name: str | None) -> dict[str, Any]:
    return {
        "task_name": task_name or f"opaque-{family}-{seed}",
        "private_suite": f"suite-{seed % 7}",
        "family_for_test_audit_only": family,
    }


def generate_affine_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[int, ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    a = rng.choice((-5, -4, -3, -2, 2, 3, 4, 5))
    b = rng.randint(-20, 20)
    values = rng.sample(range(-500, 501), demonstration_count + hidden_count)
    demos = tuple(Demonstration(value, a * value + b) for value in values[:demonstration_count])
    hidden = tuple(values[demonstration_count:])
    targets = tuple(a * value + b for value in hidden)
    return (
        TaskPackage(
            "Apply the same affine arithmetic transformation to each input number.",
            demos,
            hidden,
            OutputSchema(kind="integer"),
            _metadata("affine", seed, task_name),
        ),
        targets,
    )


def _records(rng: Random, prefix: str, count: int) -> list[list[Any]]:
    scores = rng.sample(range(-500, 501), count)
    rows = [[f"{prefix}-{index}-{rng.randrange(10_000)}", score] for index, score in enumerate(scores)]
    rng.shuffle(rows)
    return rows


def generate_sort_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[list[list[Any]], ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    demos: list[Demonstration] = []
    for index in range(demonstration_count):
        rows = _records(rng, f"d{index}", rng.randint(3, 7))
        demos.append(Demonstration(rows, sorted(rows, key=lambda row: row[1])))
    hidden: list[list[list[Any]]] = []
    targets: list[list[list[Any]]] = []
    for index in range(hidden_count):
        rows = _records(rng, f"h{index}", rng.randint(3, 9))
        hidden.append(rows)
        targets.append(sorted(rows, key=lambda row: row[1]))
    return (
        TaskPackage(
            "Sort every record by its numeric score, from the lowest score to the highest.",
            tuple(demos),
            tuple(hidden),
            OutputSchema(kind="list"),
            _metadata("sort-records", seed, task_name),
        ),
        tuple(targets),
    )


def generate_filter_count_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[int, ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    threshold = rng.randint(-20, 20)
    patterns = (
        (-8, -1, 0, 1, 9),
        (-1, 0, 20),
        (0, 1, 2),
        (-12, -3, -1, 0, 11),
        (-20, -2, 0, 5, 30),
    )
    demos: list[Demonstration] = []
    for index in range(demonstration_count):
        offsets = list(patterns[index % len(patterns)])
        if index >= len(patterns):
            offsets.extend(rng.sample(range(-30, 31), 3))
        scores = [threshold + offset for offset in offsets]
        rows = [[f"d{index}-{row_index}", score] for row_index, score in enumerate(scores)]
        rng.shuffle(rows)
        demos.append(Demonstration(rows, sum(score >= threshold for score in scores)))
    hidden: list[list[list[Any]]] = []
    targets: list[int] = []
    for index in range(hidden_count):
        scores = [rng.randint(threshold - 50, threshold + 50) for _ in range(rng.randint(3, 12))]
        rows = [[f"h{index}-{row_index}", score] for row_index, score in enumerate(scores)]
        rng.shuffle(rows)
        hidden.append(rows)
        targets.append(sum(score >= threshold for score in scores))
    return (
        TaskPackage(
            f"Count the records whose numeric score is at least {threshold}.",
            tuple(demos),
            tuple(hidden),
            OutputSchema(kind="integer"),
            _metadata("filter-count", seed, task_name),
        ),
        tuple(targets),
    )


def _graph_row(rng: Random, prefix: str, reachable: bool) -> tuple[dict[str, Any], bool]:
    nodes = [f"{prefix}-node-{index}-{rng.randrange(10_000)}" for index in range(6)]
    start, goal = nodes[0], nodes[-1]
    if reachable:
        edges = [[nodes[0], nodes[1]], [nodes[1], nodes[2]], [nodes[2], goal]]
        edges.extend([[nodes[0], nodes[3]], [nodes[3], nodes[4]]])
    else:
        edges = [[nodes[0], nodes[1]], [nodes[1], nodes[2]], [nodes[3], nodes[4]], [nodes[4], goal]]
    rng.shuffle(edges)
    return {"graph": {"edges": edges, "directed": True}, "start": start, "goal": goal}, reachable


def generate_graph_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[bool, ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    demos = tuple(
        Demonstration(*_graph_row(rng, f"d{index}", reachable=index % 2 == 0))
        for index in range(demonstration_count)
    )
    hidden_rows = [_graph_row(rng, f"h{index}", reachable=rng.choice((True, False))) for index in range(hidden_count)]
    return (
        TaskPackage(
            "Determine whether the directed graph contains a path from start to goal.",
            demos,
            tuple(row for row, _ in hidden_rows),
            OutputSchema(kind="boolean"),
            _metadata("graph-reachability", seed, task_name),
        ),
        tuple(target for _, target in hidden_rows),
    )


def _ordering_row(rng: Random, prefix: str, entity_count: int = 5) -> tuple[dict[str, Any], str]:
    entities = [f"{prefix}-entity-{index}-{rng.randrange(10_000)}" for index in range(entity_count)]
    order = list(entities)
    rng.shuffle(order)
    before = [[order[index], order[index + 1]] for index in range(len(order) - 1)]
    rng.shuffle(before)
    presented = list(entities)
    rng.shuffle(presented)
    return {
        "entities": presented,
        "before": before,
        "adjacent": [],
        "query": "last",
    }, order[-1]


def generate_ordering_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[str, ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    demos = tuple(Demonstration(*_ordering_row(rng, f"d{index}")) for index in range(demonstration_count))
    hidden_rows = [_ordering_row(rng, f"h{index}") for index in range(hidden_count)]
    return (
        TaskPackage(
            "Use the ordering constraints to return the entity that must appear last.",
            demos,
            tuple(row for row, _ in hidden_rows),
            OutputSchema(kind="string"),
            _metadata("finite-ordering", seed, task_name),
        ),
        tuple(target for _, target in hidden_rows),
    )


def generate_keyword_relation_package(
    *, seed: int,
    demonstration_count: int = 5,
    hidden_count: int = 25,
    task_name: str | None = None,
) -> tuple[TaskPackage, tuple[str, ...]]:
    _check_count(demonstration_count)
    rng = Random(seed)
    labels = (("scarlet", "alert"), ("azure", "normal"))
    fillers = ("system", "status", "report", "signal", "context", "event", "update", "incident")

    def row(index: int) -> tuple[str, str]:
        token, label = labels[index % 2]
        selected = rng.sample(fillers, 3)
        words = [selected[0], token, selected[1], selected[2], str(rng.randrange(1000))]
        rng.shuffle(words)
        return " ".join(words), label

    demos = tuple(Demonstration(*row(index)) for index in range(demonstration_count))
    hidden_rows = [row(index + demonstration_count) for index in range(hidden_count)]
    return (
        TaskPackage(
            "The token scarlet means alert, and the token azure means normal. Classify each contextual status.",
            demos,
            tuple(value for value, _ in hidden_rows),
            OutputSchema(kind="string", enum_values=("alert", "normal")),
            _metadata("keyword-relation", seed, task_name),
        ),
        tuple(target for _, target in hidden_rows),
    )
