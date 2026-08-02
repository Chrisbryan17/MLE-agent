from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence

from .atoms import AtomPool, derive_atoms
from .fibers import FiberSchema
from .program import Program
from .types import SearchConfig


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise TypeError("demonstration must provide input and output")


def _fits(program: Program, demos: Sequence[Any]) -> bool:
    try:
        return all(program.run(_demo_parts(item)[0]) == _demo_parts(item)[1] for item in demos)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, NotImplementedError):
        return False


def _common_fields(rows: Sequence[Any]) -> tuple[str, ...]:
    if not rows or not all(isinstance(item, Mapping) for item in rows):
        return ()
    names = set(str(key) for key in rows[0])
    for row in rows[1:]:
        names &= {str(key) for key in row}
    return tuple(sorted(names))


def _numeric(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _number_data(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


@dataclass(frozen=True)
class GrammarRule:
    name: str
    program: Program
    depth: int
    provenance: tuple[int, ...] = ()


@dataclass(frozen=True)
class TaskGrammar:
    instructions: str
    demonstrations: tuple[Any, ...]
    atoms: AtomPool
    programs: tuple[Program, ...]
    source_schema: FiberSchema
    target_schema: FiberSchema
    config: SearchConfig
    version: int = 1

    @property
    def sample_input(self) -> Any:
        return _demo_parts(self.demonstrations[0])[0]

    def depth(self, limit: int) -> tuple[Program, ...]:
        return tuple(item for item in self.programs if item.cost <= limit + 1)

    def can_compose(self, left: Program, right: Program) -> bool:
        try:
            middle = left.run(self.sample_input)
            right.run(middle)
            return True
        except (KeyError, TypeError, ValueError, IndexError, NotImplementedError):
            return False


def _add(candidates: dict[str, Program], data: Mapping[str, Any]) -> None:
    try:
        program = Program.parse(data)
    except (KeyError, TypeError, ValueError):
        return
    candidates.setdefault(program.digest, program)


def _affine_candidate(demos: Sequence[Any]) -> Mapping[str, Any] | None:
    pairs = [(_demo_parts(item)[0], _demo_parts(item)[1]) for item in demos]
    if not pairs or not all(_numeric(x) and _numeric(y) for x, y in pairs):
        return None
    distinct = next(((x1, y1, x2, y2) for x1, y1 in pairs for x2, y2 in pairs if x1 != x2), None)
    if distinct is None:
        return None
    x1, y1, x2, y2 = (Fraction(str(item)) for item in distinct)
    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    data = {"kind": "affine", "a": _number_data(a), "b": _number_data(b)}
    program = Program.parse(data)
    return data if _fits(program, demos) else None


def _token_candidate(instructions: str, demos: Sequence[Any], atoms: AtomPool) -> Mapping[str, Any] | None:
    pairs = list(atoms.hints.label_pairs)
    if pairs:
        data = {"kind": "token_map", "mapping": dict(pairs)}
        return data if _fits(Program.parse(data), demos) else None
    if not all(isinstance(_demo_parts(item)[0], str) and isinstance(_demo_parts(item)[1], str) for item in demos):
        return None
    by_label: dict[str, list[set[str]]] = {}
    for item in demos:
        text, label = _demo_parts(item)
        by_label.setdefault(label, []).append(set(text.split()))
    mapping: dict[str, str] = {}
    all_text = {label: set().union(*sets) for label, sets in by_label.items()}
    for label, sets in by_label.items():
        common = set.intersection(*sets)
        others = set().union(*(tokens for other, tokens in all_text.items() if other != label))
        unique = sorted(common - others)
        if not unique:
            return None
        mapping[unique[0]] = label
    data = {"kind": "token_map", "mapping": mapping}
    return data if _fits(Program.parse(data), demos) else None


def build_task_grammar(
    instructions: str,
    demonstrations: Iterable[Any],
    config: SearchConfig,
) -> TaskGrammar:
    demos = tuple(demonstrations)
    if not demos:
        raise ValueError("at least one demonstration is required")
    atoms = derive_atoms(instructions, demos)
    first_input, first_output = _demo_parts(demos[0])
    candidates: dict[str, Program] = {}

    _add(candidates, {"kind": "input"})
    affine = _affine_candidate(demos)
    if affine is not None:
        _add(candidates, affine)

    token_data = _token_candidate(instructions, demos, atoms)
    if token_data is not None:
        _add(candidates, token_data)

    inputs = [_demo_parts(item)[0] for item in demos]
    if all(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) for value in inputs):
        rows = [row for table in inputs for row in table]
        fields = _common_fields(rows)
        for field in fields:
            _add(candidates, {"kind": "project", "field": field})
            for descending in (False, True):
                order = {"kind": "order", "field": field, "descending": descending}
                _add(candidates, order)
                for output_field in fields:
                    _add(candidates, {
                        "kind": "compose",
                        "parts": [order, {"kind": "project", "field": output_field}],
                    })
            for op in ("sum", "count", "min", "max"):
                _add(candidates, {"kind": "aggregate", "op": op, "field": field})
        _add(candidates, {"kind": "aggregate", "op": "count"})

        hint_compare = atoms.hints.comparison
        compare_options: list[tuple[str, Any]] = []
        if hint_compare is not None:
            compare_options.append(hint_compare)
        for constant in atoms.constants:
            if _numeric(constant):
                compare_options.extend((op, constant) for op in ("<", "<=", "==", ">=", ">"))
        seen_compare: set[tuple[str, str]] = set()
        for filter_field in fields:
            for op, threshold in compare_options:
                key = (op, repr(threshold))
                if key in seen_compare and hint_compare is not None:
                    continue
                seen_compare.add(key)
                filter_node = {"kind": "filter", "field": filter_field, "comparison": op, "value": threshold}
                _add(candidates, {"kind": "compose", "parts": [filter_node, {"kind": "aggregate", "op": "count"}]})
                for value_field in fields:
                    _add(candidates, {
                        "kind": "compose",
                        "parts": [filter_node, {"kind": "aggregate", "op": "sum", "field": value_field}],
                    })

    if all(isinstance(value, Mapping) and ("graph" in value or "edges" in value) for value in inputs):
        _add(candidates, {"kind": "graph_reachable"})
        _add(candidates, {"kind": "shortest_path"})
        outputs = [_demo_parts(item)[1] for item in demos]
        if all(isinstance(item, str) for item in outputs):
            mapping: dict[str, str] = {}
            graph_program = Program.parse({"kind": "graph_reachable"})
            for demo in demos:
                inp, out = _demo_parts(demo)
                key = str(graph_program.run(inp)).lower()
                prior = mapping.get(key)
                if prior is not None and prior != out:
                    mapping = {}
                    break
                mapping[key] = out
            if mapping:
                _add(candidates, {
                    "kind": "label_map",
                    "source": {"kind": "graph_reachable"},
                    "mapping": mapping,
                })

    ordered = tuple(sorted(candidates.values(), key=lambda item: (item.cost, item.digest)))
    return TaskGrammar(
        instructions=instructions,
        demonstrations=demos,
        atoms=atoms,
        programs=ordered,
        source_schema=FiberSchema.infer(first_input),
        target_schema=FiberSchema.infer(first_output),
        config=config,
    )
