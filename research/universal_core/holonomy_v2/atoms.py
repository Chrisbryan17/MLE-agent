from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence

from .instructions import InstructionHints, parse_instruction_hints


@dataclass(frozen=True)
class AtomPool:
    field_paths: tuple[tuple[str, ...], ...]
    constants: tuple[Any, ...]
    labels: tuple[str, ...]
    symbols: tuple[str, ...]
    comparisons: tuple[str, ...]
    relations: tuple[tuple[str, str], ...]
    hints: InstructionHints

    def to_data(self) -> dict[str, Any]:
        return {
            "field_paths": [list(path) for path in self.field_paths],
            "constants": list(self.constants),
            "labels": list(self.labels),
            "symbols": list(self.symbols),
            "comparisons": list(self.comparisons),
            "relations": [list(item) for item in self.relations],
            "hints": self.hints.to_data(),
        }


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise TypeError("demonstration must provide input and output")


def _walk(value: Any, path: tuple[str, ...], fields: set[tuple[str, ...]], constants: set[Any], symbols: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            next_path = path + (str(key),)
            fields.add(next_path)
            _walk(item, next_path, fields, constants, symbols)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _walk(item, path, fields, constants, symbols)
        return
    if isinstance(value, bool):
        constants.add(value)
        return
    if isinstance(value, Real):
        constants.add(value)
        return
    if isinstance(value, str):
        symbols.add(value)


def derive_atoms(
    instructions: str,
    demonstrations: Iterable[Any],
    *,
    task_id: str | None = None,
) -> AtomPool:
    del task_id
    hints = parse_instruction_hints(instructions)
    fields: set[tuple[str, ...]] = set()
    constants: set[Any] = set(hints.numeric_constants)
    symbols: set[str] = set()
    labels: set[str] = {label for _, label in hints.label_pairs}
    for demo in demonstrations:
        inp, out = _demo_parts(demo)
        _walk(inp, (), fields, constants, symbols)
        _walk(out, (), fields, constants, symbols)
        if isinstance(out, str):
            labels.add(out)
        elif isinstance(out, Sequence) and not isinstance(out, (str, bytes, bytearray)):
            labels.update(item for item in out if isinstance(item, str))
    symbols.update(token for pair in hints.label_pairs for token in pair)
    return AtomPool(
        field_paths=tuple(sorted(fields)),
        constants=tuple(sorted(constants, key=repr)),
        labels=tuple(sorted(labels)),
        symbols=tuple(sorted(symbols)),
        comparisons=("!=", "<", "<=", "==", ">", ">="),
        relations=tuple(sorted(hints.priority_terms)),
        hints=hints,
    )
