"""Finite, auditable compositional program induction with active query selection.

This is a deliberately BOUNDED synthetic testbed, not universal operator invention.
No task identifiers, test labels or hidden program specifications enter inference.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

P = 7
OPS = ("roll", "reverse", "inc_first", "inc_last", "swap_mid")
Vector = tuple[int, ...]
Program = tuple[str, ...]


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def run(program: Program, value: Sequence[int]) -> Vector:
    if not isinstance(value, (tuple, list)) or len(value) != 4 or any(type(x) is not int or not 0 <= x < P for x in value):
        raise ValueError("expected a length-four vector over Z/7Z")
    state = tuple(value)
    for op in program:
        if op == "roll":
            state = state[1:] + state[:1]
        elif op == "reverse":
            state = state[::-1]
        elif op == "inc_first":
            state = ((state[0] + 1) % P,) + state[1:]
        elif op == "inc_last":
            state = state[:3] + ((state[3] + 1) % P,)
        elif op == "swap_mid":
            state = (state[0], state[2], state[1], state[3])
        else:
            raise ValueError("unknown instruction")
    return state


# Diagnostic probes used ONLY to deduplicate semantically equivalent programs.
# Program behavior on arbitrary vectors remains subject to finite-domain limits.
PROBES: tuple[Vector, ...] = (
    (0, 1, 2, 3), (3, 3, 3, 3), (0, 0, 0, 0), (6, 0, 2, 5),
    (2, 1, 0, 3), (5, 4, 3, 2), (1, 1, 0, 4), (0, 6, 0, 6),
)


def signature(program: Program) -> tuple[Vector, ...]:
    return tuple(run(program, x) for x in PROBES)


def programs(max_length: int = 3) -> tuple[Program, ...]:
    if not 1 <= max_length <= 4:
        raise ValueError("max length out of bound")
    return ((),) + tuple(seq for n in range(1, max_length + 1) for seq in itertools.product(OPS, repeat=n))


def canonical_programs(max_length: int = 3) -> tuple[Program, ...]:
    by_behavior: dict[tuple[Vector, ...], Program] = {}
    for p in programs(max_length):
        by_behavior.setdefault(signature(p), p)
    return tuple(by_behavior.values())


@dataclass(frozen=True)
class Library:
    macros: tuple[Program, ...]
    support: tuple[int, ...]
    training_digest: str


def learn_library(train: Sequence[Mapping[str, object]]) -> Library:
    """Mine macros using ONLY provided training demonstrations, never oracle programs."""
    candidates = canonical_programs(2)
    counts: Counter[Program] = Counter()
    for task in train:
        demos = task["demos"]
        fitting = [p for p in candidates if all(run(p, row["input"]) == tuple(row["output"]) for row in demos)]
        if len(fitting) == 1 and len(fitting[0]) == 2:
            counts[fitting[0]] += 1
    eligible = [(p, count) for p, count in counts.items() if count >= 3 and (len(p) - 1) * count > len(p) + 2]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return Library(tuple(p for p, _ in eligible), tuple(n for _, n in eligible), digest(train))


def order_candidates(all_programs: Sequence[Program], library: Library | None) -> tuple[Program, ...]:
    if library is None or not library.macros:
        return tuple(all_programs)
    # A macro reduces a description length, not the interpreter execution cost.
    def score(p: Program) -> tuple[int, int, Program]:
        savings = max((len(m) - 1 for m in library.macros if any(p[i:i + len(m)] == m for i in range(len(p) - len(m) + 1))), default=0)
        return (len(p) - savings, len(p), p)
    return tuple(sorted(all_programs, key=score))


def fit(demos: Sequence[Mapping[str, object]], candidates: Sequence[Program], budget: int) -> tuple[Program, ...]:
    if budget < 1:
        raise ValueError("budget must be positive")
    return tuple(p for p in candidates[:budget] if all(run(p, d["input"]) == tuple(d["output"]) for d in demos))


def entropy(values: Iterable[object]) -> float:
    counts = Counter(values)
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values()) if total else 0.0


def choose_active(fitting: Sequence[Program], pool: Sequence[Sequence[int]]) -> int:
    if not pool:
        raise ValueError("empty query pool")
    # EIG for deterministic hypotheses and uniform posterior is H(Y_q | D).
    scores = [entropy(run(p, q) for p in fitting) for q in pool]
    return max(range(len(pool)), key=lambda i: (round(scores[i], 12), -i))


def consensus(fitting: Sequence[Program], x: Sequence[int]) -> dict[str, object]:
    if not fitting:
        return {"status": "ABSTAIN", "prediction": None, "confidence": 0.0, "candidate_count": 0}
    counts = Counter(run(p, x) for p in fitting)
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return {"status": "ABSTAIN", "prediction": None, "confidence": ranked[0][1] / len(fitting), "candidate_count": len(fitting)}
    return {"status": "ACCEPTED", "prediction": list(ranked[0][0]), "confidence": ranked[0][1] / len(fitting), "candidate_count": len(fitting)}


def infer(task: Mapping[str, object], candidates: Sequence[Program], budget: int, *, query_index: int | None = None, feedback: Sequence[int] | None = None) -> dict[str, object]:
    demos = list(task["demos"])
    if query_index is not None:
        if feedback is None or not 0 <= query_index < len(task["pool"]):
            raise ValueError("query requires corresponding oracle feedback")
        demos.append({"input": task["pool"][query_index], "output": feedback})
    return consensus(fit(demos, candidates, budget), task["test_input"])
