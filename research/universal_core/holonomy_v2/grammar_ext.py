from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from .grammar import TaskGrammar, build_task_grammar
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


def _contains_filter(data: Any) -> bool:
    if isinstance(data, Mapping):
        if data.get("kind") == "filter":
            return True
        return any(_contains_filter(item) for item in data.values())
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return any(_contains_filter(item) for item in data)
    return False


def _filter_matches(data: Any, comparison: str, threshold: Any) -> bool:
    if isinstance(data, Mapping):
        if data.get("kind") == "filter":
            return data.get("comparison") == comparison and data.get("value") == threshold
        return all(_filter_matches(item, comparison, threshold) for item in data.values())
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return all(_filter_matches(item, comparison, threshold) for item in data)
    return True


def _priority_program(instructions: str, demos: Sequence[Any]) -> Program | None:
    lowered = instructions.casefold()
    match = re.search(r"return\s+([a-z0-9_-]+)\s+or\s+([a-z0-9_-]+)", lowered)
    if match is None:
        return None
    labels = [item.upper() for item in match.groups()]
    allow_label = next((item for item in labels if item.casefold().startswith("allow")), None)
    deny_label = next((item for item in labels if item.casefold().startswith("deny")), None)
    if allow_label is None or deny_label is None:
        return None
    rules: list[dict[str, Any]] = []
    emergency = re.search(
        r"during a\s+([a-z_][a-z0-9_]*),\s*(allow|deny)\s+unless\s+([a-z_][a-z0-9_]*)\s+is\s+true",
        lowered,
    )
    if emergency:
        field, action, exception = emergency.groups()
        rules.append({
            "condition": {
                "op": "and",
                "terms": [
                    {"field": field, "equals": True},
                    {"op": "not", "term": {"field": exception, "equals": True}},
                ],
            },
            "value": allow_label if action == "allow" else deny_label,
        })
    for left, right, action in re.findall(
        r"([a-z_][a-z0-9_]*)\s+together with\s+([a-z_][a-z0-9_]*)\s+(allows|denies)",
        lowered,
    ):
        rules.append({
            "condition": {"op": "and", "terms": [{"field": left, "equals": True}, {"field": right, "equals": True}]},
            "value": allow_label if action == "allows" else deny_label,
        })
    for left, one, two, action in re.findall(
        r"([a-z_][a-z0-9_]*)\s+together with\s+either\s+([a-z_][a-z0-9_]*)\s+or\s+([a-z_][a-z0-9_]*)\s+(allows|denies)",
        lowered,
    ):
        rules.append({
            "condition": {
                "op": "and",
                "terms": [
                    {"field": left, "equals": True},
                    {"op": "or", "terms": [{"field": one, "equals": True}, {"field": two, "equals": True}]},
                ],
            },
            "value": allow_label if action == "allows" else deny_label,
        })
    if not rules:
        return None
    program = Program.parse({"kind": "priority_rules", "rules": rules, "default": deny_label})
    return program if _fits(program, demos) else None


def build_task_grammar_extended(
    instructions: str,
    demonstrations: Iterable[Any],
    config: SearchConfig,
) -> TaskGrammar:
    demos = tuple(demonstrations)
    grammar = build_task_grammar(instructions, demos, config)
    programs = {item.digest: item for item in grammar.programs}
    hint = grammar.atoms.hints.comparison

    if hint is not None:
        comparison, threshold = hint
        programs = {
            digest: program
            for digest, program in programs.items()
            if not _contains_filter(program.to_data()) or _filter_matches(program.to_data(), comparison, threshold)
        }
        inputs = [_demo_parts(item)[0] for item in demos]
        if inputs and all(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) for value in inputs):
            rows = [row for table in inputs for row in table]
            fields = _common_fields(rows)
            for gate in fields:
                filter_node = {"kind": "filter", "field": gate, "comparison": comparison, "value": threshold}
                candidates = [{"kind": "compose", "parts": [filter_node, {"kind": "aggregate", "op": "count"}]}]
                candidates.extend(
                    {"kind": "compose", "parts": [filter_node, {"kind": "aggregate", "op": "sum", "field": field}]}
                    for field in fields
                )
                for data in candidates:
                    program = Program.parse(data)
                    if _fits(program, demos):
                        programs[program.digest] = program

    priority = _priority_program(instructions, demos)
    if priority is not None:
        programs[priority.digest] = priority

    ordered = tuple(sorted(programs.values(), key=lambda item: (item.cost, item.digest)))
    return replace(grammar, programs=ordered)
