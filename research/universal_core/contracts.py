from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .canonical import canonical_json_bytes, sha256_hex

_HIDDEN_TARGET_KEYS = frozenset({"target", "answer", "label", "gold"})


class FailureStatus(str, Enum):
    SOLVED = "SOLVED"
    AMBIGUOUS_TASK = "AMBIGUOUS_TASK"
    INSUFFICIENT_DEMONSTRATIONS = "INSUFFICIENT_DEMONSTRATIONS"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    OUTPUT_SCHEMA_CONFLICT = "OUTPUT_SCHEMA_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


def _contains_hidden_target(value: Any) -> bool:
    if isinstance(value, Mapping):
        lowered = {str(key).lower() for key in value}
        if lowered & _HIDDEN_TARGET_KEYS:
            return True
        return any(_contains_hidden_target(item) for item in value.values())
    if isinstance(value, tuple | list):
        return any(_contains_hidden_target(item) for item in value)
    return False


@dataclass(frozen=True)
class Demonstration:
    input: Any
    output: Any

    def to_data(self) -> dict[str, Any]:
        return {"input": self.input, "output": self.output}


@dataclass(frozen=True)
class OutputSchema:
    kind: str = "inferred"
    format: str | None = None
    enum_values: tuple[str, ...] = ()
    nullable: bool = False

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("output schema kind must be non-empty")
        object.__setattr__(self, "enum_values", tuple(self.enum_values))

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "format": self.format,
            "enum_values": list(self.enum_values),
            "nullable": self.nullable,
        }


@dataclass(frozen=True)
class TaskPackage:
    instructions: str
    demonstrations: tuple[Demonstration, ...]
    hidden_inputs: tuple[Any, ...]
    output_schema: OutputSchema = field(default_factory=OutputSchema)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    package_digest: str = field(init=False)

    def __post_init__(self) -> None:
        instructions = self.instructions.strip()
        demonstrations = tuple(self.demonstrations)
        hidden_inputs = tuple(self.hidden_inputs)
        metadata = dict(self.metadata)
        if not instructions:
            raise ValueError("instructions must be non-empty")
        if not 3 <= len(demonstrations) <= 20:
            raise ValueError("task package requires 3 to 20 demonstrations")
        if not hidden_inputs:
            raise ValueError("task package requires at least one hidden input")
        if any(_contains_hidden_target(row) for row in hidden_inputs):
            raise ValueError("hidden target fields are not permitted")
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "demonstrations", demonstrations)
        object.__setattr__(self, "hidden_inputs", hidden_inputs)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "package_digest", self.compute_digest())

    def compute_digest(self) -> str:
        payload = {
            "instructions": self.instructions,
            "demonstrations": [demo.to_data() for demo in self.demonstrations],
            "hidden_inputs": list(self.hidden_inputs),
            "output_schema": self.output_schema.to_data(),
        }
        return sha256_hex(canonical_json_bytes(payload))


@dataclass(frozen=True)
class PredictionRow:
    index: int
    prediction: Any | None
    status: FailureStatus
    confidence: float
    runtime_ms: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class AttemptResult:
    status: FailureStatus
    predictions: tuple[PredictionRow, ...]
    package_digest: str
    solver_digest: str | None
    prediction_digest: str | None
    attempt_id: str
    audit_path: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
