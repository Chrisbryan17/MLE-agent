from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class FiberKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    LIST = "LIST"
    RECORD = "RECORD"
    TABLE = "TABLE"
    GRAPH = "GRAPH"
    STATE = "STATE"
    ACTION = "ACTION"
    LABEL = "LABEL"
    CONSTRAINT = "CONSTRAINT"
    NULL = "NULL"


class NodeKind(str, Enum):
    INPUT = "input"
    LITERAL = "literal"
    FIELD = "field"
    INDEX = "index"
    COMPOSE = "compose"
    MAP = "map"
    FILTER = "filter"
    PROJECT = "project"
    ORDER = "order"
    AGGREGATE = "aggregate"
    COMPARE = "compare"
    BOOLEAN = "boolean"
    CONDITIONAL = "conditional"
    LABEL_MAP = "label_map"
    GRAPH_REACHABLE = "graph_reachable"
    SHORTEST_PATH = "shortest_path"
    FORMAT = "format"
    AFFINE = "affine"
    TOKEN_MAP = "token_map"
    MODULAR_SYMBOL = "modular_symbol"
    PRIORITY_RULES = "priority_rules"
    GRID_PATTERN_COUNT = "grid_pattern_count"
    RESOURCE_MAKESPAN = "resource_makespan"
    STATE_FOLD = "state_fold"
    STACK_REWRITE = "stack_rewrite"
    WEIGHTED_VOTE_VETO = "weighted_vote_veto"


class FailureCode(str, Enum):
    TYPE_MISMATCH = "TYPE_MISMATCH"
    GRAMMAR_EXHAUSTED = "GRAMMAR_EXHAUSTED"
    SEARCH_BUDGET_EXCEEDED = "SEARCH_BUDGET_EXCEEDED"
    MANDATORY_LOOP_FAILED = "MANDATORY_LOOP_FAILED"
    AMBIGUOUS_PROGRAM = "AMBIGUOUS_PROGRAM"
    OUTPUT_SCHEMA_CONFLICT = "OUTPUT_SCHEMA_CONFLICT"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    LOW_EVIDENCE = "LOW_EVIDENCE"


@dataclass(frozen=True)
class EngineLimits:
    max_depth: int = 6
    max_candidates: int = 50_000
    max_steps: int = 100_000
    max_loop_count: int = 2_000
    max_state_count: int = 50_000
    max_schedule_jobs: int = 8

    def __post_init__(self) -> None:
        for name, value in self.to_data().items():
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

    def to_data(self) -> dict[str, int]:
        return {
            "max_depth": self.max_depth,
            "max_candidates": self.max_candidates,
            "max_steps": self.max_steps,
            "max_loop_count": self.max_loop_count,
            "max_state_count": self.max_state_count,
            "max_schedule_jobs": self.max_schedule_jobs,
        }


@dataclass(frozen=True)
class SearchConfig:
    limits: EngineLimits = field(default_factory=EngineLimits)
    require_demo_replay: bool = True
    require_key_rename: bool = True
    require_demo_reorder: bool = True
    tier: str = "D"

    def __post_init__(self) -> None:
        if self.tier not in {"D", "H"}:
            raise ValueError("tier must be D or H")

    def to_data(self) -> dict[str, Any]:
        return {
            "limits": self.limits.to_data(),
            "require_demo_replay": self.require_demo_replay,
            "require_key_rename": self.require_key_rename,
            "require_demo_reorder": self.require_demo_reorder,
            "tier": self.tier,
        }


@dataclass(frozen=True)
class Abstention:
    code: FailureCode
    message: str
    evidence: Mapping[str, Any]

    def to_data(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "evidence": dict(self.evidence),
        }


@dataclass
class SearchStats:
    generated: int = 0
    evaluated: int = 0
    pruned_type: int = 0
    pruned_replay: int = 0
    pruned_loop: int = 0
    pruned_duplicate: int = 0
    refinement_rounds: int = 0

    def to_data(self) -> dict[str, int]:
        return {
            "generated": self.generated,
            "evaluated": self.evaluated,
            "pruned_type": self.pruned_type,
            "pruned_replay": self.pruned_replay,
            "pruned_loop": self.pruned_loop,
            "pruned_duplicate": self.pruned_duplicate,
            "refinement_rounds": self.refinement_rounds,
        }
