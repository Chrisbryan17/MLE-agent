from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import Demonstration, OutputSchema, TaskPackage

_ALIAS_GROUPS = {
    "instructions": ("instructions", "prompt"),
    "demonstrations": ("demonstrations", "examples"),
    "hidden_inputs": ("hidden_inputs", "test_inputs"),
}


def _resolve_alias(payload: Mapping[str, Any], logical: str) -> tuple[str, Any]:
    present = [name for name in _ALIAS_GROUPS[logical] if name in payload]
    if not present:
        raise ValueError(f"missing required field: {logical}")
    if len(present) > 1:
        raise ValueError(f"conflicting aliases for {logical}: {present}")
    name = present[0]
    return name, payload[name]


def _normalize_schema(raw: Any) -> OutputSchema:
    if raw is None:
        return OutputSchema()
    if isinstance(raw, str):
        return OutputSchema(kind=raw)
    if not isinstance(raw, Mapping):
        raise ValueError("output_schema must be a string or mapping")
    allowed = {"kind", "format", "enum_values", "nullable"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown output_schema fields: {sorted(unknown)}")
    return OutputSchema(
        kind=str(raw.get("kind", "inferred")),
        format=None if raw.get("format") is None else str(raw["format"]),
        enum_values=tuple(str(item) for item in raw.get("enum_values", ())),
        nullable=bool(raw.get("nullable", False)),
    )


def _normalize_demonstrations(raw: Any) -> tuple[Demonstration, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        raise ValueError("demonstrations must be a sequence")
    demos: list[Demonstration] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping) or "input" not in item or "output" not in item:
            raise ValueError(f"demonstration {index} requires input and output")
        demos.append(Demonstration(input=item["input"], output=item["output"]))
    return tuple(demos)


def _normalize_hidden(raw: Any) -> tuple[Any, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        raise ValueError("hidden_inputs must be a sequence")
    normalized: list[Any] = []
    for item in raw:
        if isinstance(item, Mapping) and set(item) == {"input"}:
            normalized.append(item["input"])
        else:
            normalized.append(item)
    return tuple(normalized)


def normalize_task_payload(payload: Mapping[str, Any]) -> TaskPackage:
    if not isinstance(payload, Mapping):
        raise ValueError("task payload must be a mapping")
    instruction_key, instructions = _resolve_alias(payload, "instructions")
    demo_key, demos = _resolve_alias(payload, "demonstrations")
    hidden_key, hidden = _resolve_alias(payload, "hidden_inputs")
    consumed = {instruction_key, demo_key, hidden_key, "output_schema"}
    metadata = {key: value for key, value in payload.items() if key not in consumed}
    return TaskPackage(
        instructions=str(instructions),
        demonstrations=_normalize_demonstrations(demos),
        hidden_inputs=_normalize_hidden(hidden),
        output_schema=_normalize_schema(payload.get("output_schema")),
        metadata=metadata,
    )
