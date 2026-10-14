"""Finite-group synchronization and explicit cycle-residual baseline.

Radii/cycles never assumed flat without modeling it: this module models the
specific Z/7Z flat-connection case. A loop residual is an error diagnostic,
not new independent evidence or an automatically learned causal factor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

MODULUS = 7


@dataclass(frozen=True)
class Edge:
    u: int
    v: int
    delta: int   # g[v] - g[u] mod MODULUS


def adjacency(n: int, edges: Iterable[Edge]) -> dict[int, list[tuple[int, int]]]:
    out: dict[int, list[tuple[int, int]]] = {i: [] for i in range(n)}
    for e in edges:
        if not (0 <= e.u < n and 0 <= e.v < n and e.u != e.v and 0 <= e.delta < MODULUS):
            raise ValueError("invalid typed edge")
        out[e.u].append((e.v, e.delta))
        out[e.v].append((e.u, (-e.delta) % MODULUS))
    return out


def tree_estimate(n: int, edges: Iterable[Edge]) -> tuple[int, ...]:
    adj = adjacency(n, edges)
    state: dict[int, int] = {0: 0}
    todo = deque([0])
    while todo:
        src = todo.popleft()
        for dst, delta in sorted(adj[src]):
            if dst not in state:
                state[dst] = (state[src] + delta) % MODULUS
                todo.append(dst)
    if len(state) != n:
        raise ValueError("disconnected graph cannot synchronize gauges")
    return tuple(state[i] for i in range(n))


def cycle_residuals(edges: Iterable[Edge]) -> dict[tuple[int, int, int], int]:
    """Signed residual for each unique triangle, relative edge orientation."""
    e = tuple(edges)
    graph = {}
    for item in e:
        graph[item.u, item.v] = item.delta
        graph[item.v, item.u] = (-item.delta) % MODULUS
    nodes = sorted({item.u for item in e} | {item.v for item in e})
    out = {}
    for ai, a in enumerate(nodes):
        for bi in range(ai+1, len(nodes)):
            b = nodes[bi]
            for c in nodes[bi+1:]:
                if (a,b) in graph and (b,c) in graph and (c,a) in graph:
                    out[a,b,c] = (graph[a,b] + graph[b,c] + graph[c,a]) % MODULUS
    return out


def loss(state: Iterable[int], edges: Iterable[Edge]) -> int:
    s = tuple(state)
    return sum((s[e.v] - s[e.u]) % MODULUS != e.delta for e in edges)


def robust_estimate(n: int, edges: Iterable[Edge], *, rounds: int = 40) -> tuple[int, ...]:
    """Deterministic local optimization of robust edge disagreement count.

    Strong conventional graph-estimation baseline; not a holonomy-specific method.
    May get trapped in local minima and provides no general recovery guarantee.
    """
    es = tuple(edges)
    seed = tree_estimate(n, es)
    adj = adjacency(n, es)
    best = list(seed)
    for _ in range(rounds):
        changed = False
        for v in range(1, n):
            def local_cost(value: int) -> int:
                return sum((value + delta - best[nbr]) % MODULUS != 0 for nbr, delta in adj[v])
            c = [(local_cost(z), z != best[v], z) for z in range(MODULUS)]
            new = min(c)[2]
            if new != best[v]:
                best[v] = new
                changed = True
        if not changed:
            break
    return tuple(best)
