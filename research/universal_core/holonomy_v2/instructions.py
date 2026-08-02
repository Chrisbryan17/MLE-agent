from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class InstructionHints:
    numeric_constants: tuple[int | float, ...] = ()
    comparison: tuple[str, int | float] | None = None
    order_direction: str | None = None
    field_mentions: tuple[str, ...] = ()
    tie_break_fields: tuple[str, ...] = ()
    priority_terms: tuple[tuple[str, str], ...] = ()
    phase_terms: tuple[str, ...] = ()
    label_pairs: tuple[tuple[str, str], ...] = ()
    modulus: int | None = None
    coefficients: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    aggregate: str | None = None
    cycle: tuple[str, ...] = ()

    def to_data(self) -> dict[str, object]:
        return {
            "numeric_constants": list(self.numeric_constants),
            "comparison": None if self.comparison is None else list(self.comparison),
            "order_direction": self.order_direction,
            "field_mentions": list(self.field_mentions),
            "tie_break_fields": list(self.tie_break_fields),
            "priority_terms": [list(item) for item in self.priority_terms],
            "phase_terms": list(self.phase_terms),
            "label_pairs": [list(item) for item in self.label_pairs],
            "modulus": self.modulus,
            "coefficients": dict(self.coefficients),
            "aggregate": self.aggregate,
            "cycle": list(self.cycle),
        }


def _number(raw: str) -> int | float:
    return float(raw) if "." in raw else int(raw)


def parse_instruction_hints(text: str) -> InstructionHints:
    lowered = text.casefold()
    numbers = tuple(sorted({_number(item) for item in re.findall(r"-?\d+(?:\.\d+)?", lowered)}, key=repr))

    comparison = None
    patterns = (
        (r"(?:at least|no less than)\s+(-?\d+(?:\.\d+)?)", ">="),
        (r"(?:greater than|more than|above)\s+(-?\d+(?:\.\d+)?)", ">"),
        (r"(?:at most|no more than)\s+(-?\d+(?:\.\d+)?)", "<="),
        (r"(?:less than|fewer than|below)\s+(-?\d+(?:\.\d+)?)", "<"),
        (r"(?:equal to|equals|exactly)\s+(-?\d+(?:\.\d+)?)", "=="),
    )
    for pattern, op in patterns:
        match = re.search(pattern, lowered)
        if match:
            comparison = (op, _number(match.group(1)))
            break

    if any(token in lowered for token in ("descending", "greatest", "largest", "least magnitude")):
        direction = "descending"
    elif any(token in lowered for token in ("ascending", "increasing", "smallest", "least to greatest")):
        direction = "ascending"
    else:
        direction = None

    field_mentions: set[str] = set()
    field_patterns = (
        r"(?:order|arrange|sort)\s+(?:entries\s+)?by\s+([a-z_][a-z0-9_]*)",
        r"whose\s+([a-z_][a-z0-9_]*)",
        r"sum\s+the\s+([a-z_][a-z0-9_]*)",
        r"return\s+(?:only\s+)?the\s+([a-z_][a-z0-9_]*)",
        r"from\s+([a-z_][a-z0-9_]*)\s+to\s+([a-z_][a-z0-9_]*)",
    )
    for pattern in field_patterns:
        for match in re.finditer(pattern, lowered):
            field_mentions.update(group for group in match.groups() if group)

    tie_fields = tuple(sorted(set(re.findall(r"ties?\s+by\s+([a-z_][a-z0-9_]*)", lowered))))
    priority = tuple(sorted(set(re.findall(r"([a-z_][a-z0-9_]*)\s+overrides\s+([a-z_][a-z0-9_]*)", lowered))))
    phases = tuple(sorted(set(re.findall(r"phase\s+(?:[a-z]+|\d+)", lowered))))
    label_pairs = tuple(sorted(set(re.findall(
        r"(?:the\s+)?token\s+([a-z0-9_-]+)\s+means\s+([a-z0-9_-]+)",
        lowered,
    ))))
    modulus_match = re.search(r"(?:modulo|mod)\s+(\d+)", lowered)
    modulus = int(modulus_match.group(1)) if modulus_match else None
    cycle_match = re.search(r"cycle\s+in\s+this\s+order:\s*([^.]+)", lowered)
    cycle = () if cycle_match is None else tuple(
        token.strip() for token in cycle_match.group(1).split(",") if token.strip()
    )
    coeff = {name: int(raw) for raw, name in re.findall(r"(\d+)\s*\*\s*([a-z_][a-z0-9_]*)", lowered)}

    if "sum" in lowered:
        aggregate = "sum"
    elif "how many" in lowered or "count" in lowered:
        aggregate = "count"
    elif "minimum" in lowered or "shortest" in lowered:
        aggregate = "min"
    elif "maximum" in lowered or "greatest" in lowered:
        aggregate = "max"
    else:
        aggregate = None

    return InstructionHints(
        numeric_constants=numbers,
        comparison=comparison,
        order_direction=direction,
        field_mentions=tuple(sorted(field_mentions)),
        tie_break_fields=tie_fields,
        priority_terms=priority,
        phase_terms=phases,
        label_pairs=label_pairs,
        modulus=modulus,
        coefficients=MappingProxyType(dict(sorted(coeff.items()))),
        aggregate=aggregate,
        cycle=cycle,
    )
