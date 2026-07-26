#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import itertools
import re
from typing import Iterable

try:
    import z3  # type: ignore
except ImportError:  # Local smoke tests can use the finite fallback.
    z3 = None


@dataclass(frozen=True)
class Problem:
    size: int
    categories: dict[str, tuple[str, ...]]
    clues: tuple[str, ...]
    question: str


@dataclass(frozen=True)
class Relation:
    kind: str
    values: tuple[str, ...]
    amount: int | None = None


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}


def _category_key(prefix: str) -> str:
    text = prefix.strip().lower()
    text = re.sub(r"^everyone\s+", "", text)
    text = re.sub(r"\b(?:has|have|likes|owns|drives|plays|supports|smokes|drinks|lives in|reads|is)\b", " ", text)
    text = re.sub(r"\ba\s+different\b|\bdifferent\b|\bfavorite\b|\btype of\b|\bkind of\b", " ", text)
    tokens = re.findall(r"[a-z0-9-]+", text)
    return tokens[-1] if tokens else "category"


def parse_problem(text: str) -> Problem:
    size_match = re.search(r"There are\s+(\d+)\s+people", text, re.I)
    if not size_match:
        raise ValueError("missing puzzle size")
    size = int(size_match.group(1))

    header = text.split("Using the clues provided below", 1)[0]
    categories: dict[str, tuple[str, ...]] = {}
    for raw_line in header.splitlines()[1:]:
        line = raw_line.strip()
        if not line.lower().startswith("everyone") or ":" not in line:
            continue
        prefix, values_text = line.split(":", 1)
        values = tuple(value.strip().rstrip(".") for value in values_text.rstrip(".").split(",") if value.strip())
        if len(values) != size:
            raise ValueError(f"category has {len(values)} values, expected {size}: {line}")
        key = _category_key(prefix)
        if key in categories:
            suffix = 2
            while f"{key}_{suffix}" in categories:
                suffix += 1
            key = f"{key}_{suffix}"
        categories[key] = values
    if not categories:
        raise ValueError("no categories parsed")

    clues = tuple(
        match.group(1).strip()
        for match in re.finditer(
            r"(?:^|\n)Clue\s+\d+:\s*(.*?)(?=\nClue\s+\d+:|\nQuestion:|\Z)",
            text,
            re.S | re.I,
        )
    )
    question_match = re.search(r"(?:^|\n)Question:\s*(.*?)\s*$", text, re.S | re.I)
    if not question_match:
        raise ValueError("missing question")
    return Problem(size=size, categories=categories, clues=clues, question=question_match.group(1).strip())


def _all_values(problem: Problem) -> tuple[str, ...]:
    return tuple(value for values in problem.categories.values() for value in values)


def _mentions(text: str, values: Iterable[str]) -> list[str]:
    lowered = text.lower()
    hits: list[tuple[int, int, str]] = []
    for value in sorted(values, key=len, reverse=True):
        pattern = r"(?<![\w-])" + re.escape(value.lower()) + r"(?![\w-])"
        for match in re.finditer(pattern, lowered):
            hits.append((match.start(), match.end(), value))
    hits.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    result: list[str] = []
    for start, end, value in hits:
        if any(not (end <= left or start >= right) for left, right in occupied):
            continue
        occupied.append((start, end))
        result.append(value)
    return result


def compile_clue(clue: str, all_values: Iterable[str]) -> Relation:
    low = clue.lower().strip().rstrip(".")
    values = _mentions(clue, all_values)
    if not values:
        raise ValueError(f"no values in clue: {clue}")

    if "at one of the ends" in low or "at either end" in low:
        return Relation("end", (values[0],))
    if "at the far left" in low or "in the first position" in low:
        return Relation("position", (values[0],), 1)
    position = re.search(r"(?:in|at) (?:the )?(\d+)(?:st|nd|rd|th)? position", low)
    if position:
        return Relation("position", (values[0],), int(position.group(1)))
    if "immediately to the left of" in low or "directly to the left of" in low:
        return Relation("immediate_left", (values[0], values[1]))
    if "immediately to the right of" in low or "directly to the right of" in low:
        return Relation("immediate_right", (values[0], values[1]))
    if "somewhere in between" in low and "in that order" in low and len(values) >= 3:
        return Relation("between_ordered", (values[0], values[1], values[2]))
    if "immediately between" in low and len(values) >= 3:
        return Relation("between_immediate", (values[0], values[1], values[2]))
    if "somewhere to the left of" in low:
        return Relation("left", (values[0], values[1]))
    if "somewhere to the right of" in low:
        return Relation("right", (values[0], values[1]))
    if "is not next to" in low or "isn't next to" in low:
        return Relation("not_next", (values[0], values[1]))
    if "next to" in low:
        return Relation("next", (values[0], values[1]))
    if len(values) >= 2 and re.search(r"\b(?:is|are) not\b|\bisn't\b|\baren't\b", low):
        return Relation("not_equal", (values[0], values[1]))
    if len(values) >= 2:
        return Relation("equal", (values[0], values[1]))
    raise ValueError(f"uncompiled clue: {clue}")


def _relation_holds(relation: Relation, assignment: dict[str, int], size: int) -> bool:
    values = relation.values
    if any(value not in assignment for value in values):
        return True
    pos = [assignment[value] for value in values]
    if relation.kind == "end":
        return pos[0] in {1, size}
    if relation.kind == "position":
        return pos[0] == relation.amount
    if relation.kind == "immediate_left":
        return pos[0] + 1 == pos[1]
    if relation.kind == "immediate_right":
        return pos[0] == pos[1] + 1
    if relation.kind == "left":
        return pos[0] < pos[1]
    if relation.kind == "right":
        return pos[0] > pos[1]
    if relation.kind == "next":
        return abs(pos[0] - pos[1]) == 1
    if relation.kind == "not_next":
        return abs(pos[0] - pos[1]) != 1
    if relation.kind == "equal":
        return pos[0] == pos[1]
    if relation.kind == "not_equal":
        return pos[0] != pos[1]
    if relation.kind == "between_ordered":
        return pos[1] < pos[0] < pos[2]
    if relation.kind == "between_immediate":
        return abs(pos[0] - pos[1]) == 1 and abs(pos[0] - pos[2]) == 1 and pos[1] != pos[2]
    raise ValueError(relation.kind)


def _query_value(problem: Problem) -> str:
    values = _mentions(problem.question, _all_values(problem))
    if len(values) != 1:
        raise ValueError(f"question must mention one value, found {values}: {problem.question}")
    return values[0]


def _solve_small(problem: Problem, relations: list[Relation]) -> str | None:
    categories = list(problem.categories.values())
    target = _query_value(problem)
    possible: set[int] = set()

    def recurse(index: int, assignment: dict[str, int]) -> None:
        if len(possible) > 1:
            return
        if index == len(categories):
            if all(_relation_holds(relation, assignment, problem.size) for relation in relations):
                possible.add(assignment[target])
            return
        values = categories[index]
        for permutation in itertools.permutations(range(1, problem.size + 1)):
            updated = dict(assignment)
            updated.update(zip(values, permutation))
            if all(_relation_holds(relation, updated, problem.size) for relation in relations):
                recurse(index + 1, updated)

    recurse(0, {})
    return str(next(iter(possible))) if len(possible) == 1 else None


def _z3_expression(relation: Relation, variables: dict[str, object], size: int):
    p = [variables[value] for value in relation.values]
    if relation.kind == "end":
        return z3.Or(p[0] == 1, p[0] == size)
    if relation.kind == "position":
        return p[0] == relation.amount
    if relation.kind == "immediate_left":
        return p[0] + 1 == p[1]
    if relation.kind == "immediate_right":
        return p[0] == p[1] + 1
    if relation.kind == "left":
        return p[0] < p[1]
    if relation.kind == "right":
        return p[0] > p[1]
    if relation.kind == "next":
        return z3.Abs(p[0] - p[1]) == 1
    if relation.kind == "not_next":
        return z3.Abs(p[0] - p[1]) != 1
    if relation.kind == "equal":
        return p[0] == p[1]
    if relation.kind == "not_equal":
        return p[0] != p[1]
    if relation.kind == "between_ordered":
        return z3.And(p[1] < p[0], p[0] < p[2])
    if relation.kind == "between_immediate":
        return z3.And(z3.Abs(p[0] - p[1]) == 1, z3.Abs(p[0] - p[2]) == 1, p[1] != p[2])
    raise ValueError(relation.kind)


def _solve_z3(problem: Problem, relations: list[Relation]) -> str | None:
    variables = {
        value: z3.Int("p_" + re.sub(r"\W+", "_", value).strip("_") + f"_{index}")
        for index, value in enumerate(_all_values(problem))
    }
    solver = z3.Solver()
    for variable in variables.values():
        solver.add(variable >= 1, variable <= problem.size)
    for values in problem.categories.values():
        solver.add(z3.Distinct([variables[value] for value in values]))
    for relation in relations:
        solver.add(_z3_expression(relation, variables, problem.size))
    if solver.check() != z3.sat:
        return None
    target = variables[_query_value(problem)]
    possible = []
    for position in range(1, problem.size + 1):
        solver.push()
        solver.add(target == position)
        if solver.check() == z3.sat:
            possible.append(position)
        solver.pop()
    return str(possible[0]) if len(possible) == 1 else None


def solve(text: str) -> str | None:
    problem = parse_problem(text)
    all_values = _all_values(problem)
    relations = [compile_clue(clue, all_values) for clue in problem.clues]
    if z3 is not None:
        return _solve_z3(problem, relations)
    if problem.size <= 4:
        return _solve_small(problem, relations)
    raise RuntimeError("z3-solver is required for puzzles larger than 4x4")
