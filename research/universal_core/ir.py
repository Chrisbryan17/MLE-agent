from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .canonical import canonical_json_bytes, sha256_hex


class ValueType(str, Enum):
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    SYMBOL = "SYMBOL"
    ENUM = "ENUM"
    LIST = "LIST"
    SET = "SET"
    MAP = "MAP"
    RECORD = "RECORD"
    TABLE = "TABLE"
    GRAPH = "GRAPH"
    INTERVAL = "INTERVAL"
    COORDINATE = "COORDINATE"
    DISTRIBUTION = "DISTRIBUTION"
    UNKNOWN = "UNKNOWN"


class RelationKind(str, Enum):
    GENERIC = "GENERIC"
    LOGICAL = "LOGICAL"
    ORDERING = "ORDERING"
    TEMPORAL = "TEMPORAL"
    SPATIAL = "SPATIAL"
    GRAPH = "GRAPH"
    CAUSAL = "CAUSAL"
    TAXONOMIC = "TAXONOMIC"


class Capability(str, Enum):
    PARSE = "PARSE"
    EXTRACT = "EXTRACT"
    MAP = "MAP"
    FILTER = "FILTER"
    GROUP = "GROUP"
    JOIN = "JOIN"
    PROJECT = "PROJECT"
    SORT = "SORT"
    COUNT = "COUNT"
    AGGREGATE = "AGGREGATE"
    COMPARE = "COMPARE"
    RANK = "RANK"
    UNIFY = "UNIFY"
    DEDUCE = "DEDUCE"
    PROPAGATE = "PROPAGATE"
    SEARCH = "SEARCH"
    BACKTRACK = "BACKTRACK"
    SOLVE_CONSTRAINTS = "SOLVE_CONSTRAINTS"
    TRAVERSE_GRAPH = "TRAVERSE_GRAPH"
    COMPUTE_PATH = "COMPUTE_PATH"
    EVALUATE_EXPRESSION = "EVALUATE_EXPRESSION"
    TRANSFORM_COORDINATES = "TRANSFORM_COORDINATES"
    SIMULATE = "SIMULATE"
    CLASSIFY = "CLASSIFY"
    FORMAT = "FORMAT"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    value_type: ValueType
    required: bool = True
    description: str | None = None
    provenance: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("field name must be non-empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "provenance", tuple(int(item) for item in self.provenance))

    def to_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value_type": self.value_type.value,
            "required": self.required,
            "description": self.description,
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class RelationSpec:
    name: str
    kind: RelationKind
    argument_types: tuple[ValueType, ...]
    properties: tuple[str, ...] = ()
    provenance: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("relation name must be non-empty")
        if not self.argument_types:
            raise ValueError("relation must define at least one argument type")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "argument_types", tuple(self.argument_types))
        object.__setattr__(self, "properties", tuple(sorted(set(self.properties))))
        object.__setattr__(self, "provenance", tuple(int(item) for item in self.provenance))

    def to_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "argument_types": [item.value for item in self.argument_types],
            "properties": list(self.properties),
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class ConstraintSpec:
    kind: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    expression: str | None = None
    provenance: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        kind = self.kind.strip()
        if not kind:
            raise ValueError("constraint kind must be non-empty")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "provenance", tuple(int(item) for item in self.provenance))

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "parameters": dict(self.parameters),
            "expression": self.expression,
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class TaskSpec:
    input_type: ValueType
    output_type: ValueType
    fields: tuple[FieldSpec, ...] = ()
    relations: tuple[RelationSpec, ...] = ()
    constraints: tuple[ConstraintSpec, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    objective: str = ""
    output_format: str | None = None
    order_sensitive: bool = True
    confidence: float = 1.0
    provenance: tuple[int, ...] = ()
    competing_hypotheses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        fields = tuple(self.fields)
        relations = tuple(self.relations)
        constraints = tuple(self.constraints)
        capabilities = tuple(self.capabilities)
        field_names = [item.name for item in fields]
        relation_names = [item.name for item in relations]
        if len(field_names) != len(set(field_names)):
            raise ValueError("duplicate field names are not permitted")
        if len(relation_names) != len(set(relation_names)):
            raise ValueError("duplicate relation names are not permitted")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "constraints", constraints)
        object._setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "objective", self.objective.strip())
        object.__setattr__(self, "provenance", tuple(int(item) for item in self.provenance))
        object.__setattr__(self, "competing_hypotheses", tuple(self.competing_hypotheses))

    def to_data(self) -> dict[str, Any]:
        return {
            "input_type": self.input_type.value,
            "output_type": self.output_type.value,
            "fields": [item.to_data() for item in sorted(self.fields, key=lambda item: item.name)],
            "relations": [item.to_data() for item in sorted(self.relations, key=lambda item: item.name)],
            "constraints": [
                item.to_data()
                for item in sorted(
                    self.constraints,
                    key=lambda item: (item.kind, canonical_json_bytes(item.to_data())),
                )
            ],
            "capabilities": sorted({item.value for item in self.capabilities}),
            "objective": self.objective,
            "output_format": self.output_format,
            "order_sensitive": self.order_sensitive,
            "confidence": self.confidence,
            "provenance": list(self.provenance),
            "competing_hypotheses": list(self.competing_hypotheses),
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))
