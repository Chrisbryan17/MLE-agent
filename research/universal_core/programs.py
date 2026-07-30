from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TYPE_CHECKING

from .canonical import canonical_json_bytes, sha256_hex

if TYPE_CHECKING:
    from .operators import OperatorRegistry


@dataclass(frozen=True)
class OperatorStep:
    operator: str
    source: str
    target: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.operator.strip():
            raise ValueError("operator name must be non-empty")
        if not self.source.strip():
            raise ValueError("operator source must be non-empty")
        if not self.target.strip():
            raise ValueError("operator target must be non-empty")
        object.__setattr__(self, "arguments", dict(self.arguments))

    def to_data(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "source": self.source,
            "target": self.target,
            "arguments": dict(self.arguments),
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "OperatorStep":
        allowed = {"operator", "source", "target", "arguments"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown operator step fields: {sorted(unknown)}")
        return cls(
            operator=str(data["operator"]),
            source=str(data.get("source", "$input")),
            target=str(data.get("target", "$output")),
            arguments=data.get("arguments", {}),
        )


@dataclass(frozen=True)
class OperatorProgram:
    steps: tuple[OperatorStep, ...]
    version: int = 1

    def __post_init__(self) -> None:
        steps = tuple(self.steps)
        if not steps:
            raise ValueError("operator program requires at least one step")
        if self.version != 1:
            raise ValueError(f"unsupported operator program version: {self.version}")
        object.__setattr__(self, "steps", steps)

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": "operator_program",
            "version": self.version,
            "steps": [step.to_data() for step in self.steps],
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "OperatorProgram":
        allowed = {"kind", "version", "steps"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown operator program fields: {sorted(unknown)}")
        if data.get("kind", "operator_program") != "operator_program":
            raise ValueError("program kind must be operator_program")
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("operator program steps must be a list")
        return cls(
            tuple(OperatorStep.from_data(step) for step in raw_steps),
            version=int(data.get("version", 1)),
        )

    def run(self, value: Any, registry: "OperatorRegistry | None" = None) -> Any:
        if registry is None:
            from .operators import default_registry

            registry = default_registry()
        context: dict[str, Any] = {"$input": value}
        for step in self.steps:
            if step.source not in context:
                raise KeyError(f"unknown program source: {step.source}")
            result = registry.execute(step.operator, context[step.source], step.arguments)
            context[step.target] = result
        if "$output" not in context:
            raise ValueError("operator program did not produce $output")
        return context["$output"]
