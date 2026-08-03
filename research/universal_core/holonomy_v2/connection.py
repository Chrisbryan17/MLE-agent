from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .fibers import FiberSchema
from .grammar import TaskGrammar
from .program import Program


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise TypeError("demonstration must provide input and output")


@dataclass(frozen=True)
class TransportEdge:
    source: FiberSchema
    target: FiberSchema
    program: Program
    provenance: tuple[int, ...]
    cost: int


@dataclass(frozen=True)
class ConnectionGraph:
    vertices: tuple[FiberSchema, ...]
    edges: tuple[TransportEdge, ...]

    @classmethod
    def from_demonstrations(cls, demonstrations: Iterable[Any], grammar: TaskGrammar) -> "ConnectionGraph":
        demos = tuple(demonstrations)
        edges: list[TransportEdge] = []
        vertices: set[FiberSchema] = {grammar.source_schema, grammar.target_schema}
        for program in grammar.programs:
            provenance: list[int] = []
            outputs: list[Any] = []
            for index, demo in enumerate(demos):
                inp, expected = _demo_parts(demo)
                try:
                    actual = program.run(inp)
                except (KeyError, TypeError, ValueError, IndexError, NotImplementedError):
                    continue
                outputs.append(actual)
                if actual == expected:
                    provenance.append(index)
            if len(provenance) != len(demos) or not outputs:
                continue
            target = FiberSchema.infer(outputs[0])
            vertices.add(target)
            edges.append(TransportEdge(grammar.source_schema, target, program, tuple(provenance), program.cost))
        return cls(
            vertices=tuple(sorted(vertices, key=lambda item: repr(item.to_data()))),
            edges=tuple(sorted(edges, key=lambda item: (item.cost, item.program.digest))),
        )

    def find_path(
        self,
        source: FiberSchema,
        target: FiberSchema,
        *,
        max_edges: int,
    ) -> tuple[tuple[TransportEdge, ...], ...]:
        if max_edges <= 0:
            raise ValueError("max_edges must be positive")
        paths: list[tuple[TransportEdge, ...]] = []
        frontier: list[tuple[FiberSchema, tuple[TransportEdge, ...]]] = [(source, ())]
        while frontier:
            current, path = frontier.pop(0)
            if path and current == target:
                paths.append(path)
                continue
            if len(path) >= max_edges:
                continue
            for edge in self.edges:
                if edge.source != current:
                    continue
                if any(item.program.digest == edge.program.digest for item in path):
                    continue
                frontier.append((edge.target, path + (edge,)))
        return tuple(sorted(paths, key=lambda path: (sum(item.cost for item in path), tuple(item.program.digest for item in path))))

    def compose(self, path: Sequence[TransportEdge]) -> Program:
        if not path:
            raise ValueError("path may not be empty")
        if len(path) == 1:
            return path[0].program
        return Program.parse({"kind": "compose", "parts": [item.program.to_data() for item in path]})
