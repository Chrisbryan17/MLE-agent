from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping, Sequence

from .types import FiberKind


@dataclass(frozen=True)
class FiberSchema:
    kind: FiberKind
    item: "FiberSchema | None" = None
    fields: tuple[tuple[str, "FiberSchema"], ...] = ()
    nullable: bool = False

    @classmethod
    def infer(cls, value: Any) -> "FiberSchema":
        if value is None:
            return cls(FiberKind.NULL, nullable=True)
        if isinstance(value, bool):
            return cls(FiberKind.BOOLEAN)
        if isinstance(value, int):
            return cls(FiberKind.INTEGER)
        if isinstance(value, Real):
            return cls(FiberKind.NUMBER)
        if isinstance(value, str):
            return cls(FiberKind.STRING)
        if isinstance(value, Mapping):
            if "edges" in value:
                return cls(FiberKind.GRAPH)
            return cls(
                FiberKind.RECORD,
                fields=tuple(
                    (str(key), cls.infer(item))
                    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                ),
            )
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if not value:
                return cls(FiberKind.LIST, item=cls(FiberKind.UNKNOWN))
            item_schemas = [cls.infer(item) for item in value]
            merged = _merge_schemas(item_schemas)
            kind = FiberKind.TABLE if merged.kind is FiberKind.RECORD else FiberKind.LIST
            return cls(kind, item=merged)
        return cls(FiberKind.UNKNOWN)

    @classmethod
    def state(cls, fields: Mapping[str, "FiberSchema"]) -> "FiberSchema":
        return cls(
            FiberKind.STATE,
            fields=tuple(sorted(((str(k), v) for k, v in fields.items()), key=lambda pair: pair[0])),
        )

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "item": None if self.item is None else self.item.to_data(),
            "fields": [[name, schema.to_data()] for name, schema in self.fields],
            "nullable": self.nullable,
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "FiberSchema":
        item_data = data.get("item")
        return cls(
            kind=FiberKind(str(data["kind"])),
            item=None if item_data is None else cls.from_data(item_data),
            fields=tuple((str(name), cls.from_data(value)) for name, value in data.get("fields", ())),
            nullable=bool(data.get("nullable", False)),
        )


@dataclass(frozen=True)
class FiberValue:
    value: Any
    schema: FiberSchema

    @classmethod
    def of(cls, value: Any) -> "FiberValue":
        return cls(value=value, schema=FiberSchema.infer(value))


@dataclass(frozen=True)
class TransportSignature:
    source: FiberSchema
    target: FiberSchema

    def to_data(self) -> dict[str, Any]:
        return {"source": self.source.to_data(), "target": self.target.to_data()}


@dataclass(frozen=True)
class Observation:
    index: int
    input: FiberValue
    output: FiberValue

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("observation index must be nonnegative")


def _merge_schemas(items: Sequence[FiberSchema]) -> FiberSchema:
    if not items:
        return FiberSchema(FiberKind.UNKNOWN)
    first = items[0]
    if all(item == first for item in items[1:]):
        return first
    kinds = {item.kind for item in items}
    if kinds <= {FiberKind.INTEGER, FiberKind.NUMBER}:
        return FiberSchema(FiberKind.NUMBER)
    if len(kinds) == 1 and first.kind is FiberKind.RECORD:
        field_names = set(name for name, _ in first.fields)
        for item in items[1:]:
            field_names &= {name for name, _ in item.fields}
        merged_fields: list[tuple[str, FiberSchema]] = []
        for name in sorted(field_names):
            merged_fields.append((name, _merge_schemas([dict(item.fields)[name] for item in items])))
        return FiberSchema(FiberKind.RECORD, fields=tuple(merged_fields))
    return FiberSchema(FiberKind.UNKNOWN)


def schema_distance(left: FiberSchema, right: FiberSchema) -> int:
    distance = 0
    if left.kind is not right.kind:
        distance += 1
    if left.nullable != right.nullable:
        distance += 1
    if (left.item is None) != (right.item is None):
        distance += 1
    elif left.item is not None and right.item is not None:
        distance += schema_distance(left.item, right.item)
    left_fields = dict(left.fields)
    right_fields = dict(right.fields)
    distance += len(set(left_fields) ^ set(right_fields))
    for name in set(left_fields) & set(right_fields):
        distance += schema_distance(left_fields[name], right_fields[name])
    return distance
