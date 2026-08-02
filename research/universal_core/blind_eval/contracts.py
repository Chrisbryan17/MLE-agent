from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Mapping, Sequence

from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.contracts import Demonstration, OutputSchema, TaskPackage

from .constants import FROZEN_CORE_COMMIT, PROTOCOL_VERSION, ZERO_DIGEST

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


def require_fields(data: Mapping[str, Any], *, name: str, allowed: set[str], required: set[str]) -> None:
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must be a mapping")
    unknown = set(data) - allowed
    missing = required - set(data)
    if unknown:
        raise ValueError(f"unknown {name} fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing {name} fields: {sorted(missing)}")


def require_digest(value: object, name: str) -> str:
    text = str(value)
    if not _HEX64.fullmatch(text):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return text


def require_commit(value: object, name: str = "commit") -> str:
    text = str(value)
    if not _HEX40.fullmatch(text):
        raise ValueError(f"{name} must be a lowercase 40-character git commit")
    return text


def require_id(value: object, name: str) -> str:
    text = str(value)
    if not _OPAQUE_ID.fullmatch(text):
        raise ValueError(f"{name} must be an opaque identifier")
    return text


def require_timestamp(value: object, name: str) -> str:
    text = str(value)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be an RFC3339 UTC timestamp")
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC3339 UTC timestamp") from exc
    return text


def timestamp_value(value: str) -> datetime:
    return datetime.fromisoformat(require_timestamp(value, "timestamp")[:-1] + "+00:00")


def require_finite_tree(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            require_finite_tree(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            require_finite_tree(item, f"{path}[{index}]")


def _demonstration_from_data(data: Mapping[str, Any]) -> Demonstration:
    require_fields(data, name="Demonstration", allowed={"input", "output"}, required={"input", "output"})
    return Demonstration(data["input"], data["output"])


def _schema_from_data(data: Mapping[str, Any]) -> OutputSchema:
    require_fields(data, name="OutputSchema", allowed={"kind", "format", "enum_values", "nullable"}, required={"kind"})
    return OutputSchema(
        kind=str(data["kind"]),
        format=None if data.get("format") is None else str(data["format"]),
        enum_values=tuple(str(item) for item in data.get("enum_values", ())),
        nullable=bool(data.get("nullable", False)),
    )


class GeneralizationLevel(IntEnum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4


class RowOutcome(str, Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    ABSTAINED = "ABSTAINED"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    OUTPUT_SCHEMA_CONFLICT = "OUTPUT_SCHEMA_CONFLICT"
    INVALID_SUBMISSION = "INVALID_SUBMISSION"
    EVALUATOR_DEFECT_EXCLUSION = "EVALUATOR_DEFECT_EXCLUSION"


class EquivalenceKind(str, Enum):
    EXACT = "EXACT"
    CASEFOLD_STRING = "CASEFOLD_STRING"
    UNORDERED_SEQUENCE = "UNORDERED_SEQUENCE"
    RATIONAL_NUMBER = "RATIONAL_NUMBER"
    NUMERIC_TOLERANCE = "NUMERIC_TOLERANCE"
    GRAPH_EDGE_SET = "GRAPH_EDGE_SET"


@dataclass(frozen=True)
class EquivalenceRule:
    kind: EquivalenceKind = EquivalenceKind.EXACT
    absolute_tolerance: float = 0.0
    relative_tolerance: float = 0.0
    directed_graph: bool = True

    def __post_init__(self) -> None:
        for name, value in (("absolute_tolerance", self.absolute_tolerance), ("relative_tolerance", self.relative_tolerance)):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "absolute_tolerance": self.absolute_tolerance,
            "relative_tolerance": self.relative_tolerance,
            "directed_graph": self.directed_graph,
        }

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "EquivalenceRule":
        require_fields(data, name="EquivalenceRule", allowed={"kind", "absolute_tolerance", "relative_tolerance", "directed_graph"}, required={"kind"})
        return cls(
            EquivalenceKind(str(data["kind"])),
            float(data.get("absolute_tolerance", 0.0)),
            float(data.get("relative_tolerance", 0.0)),
            bool(data.get("directed_graph", True)),
        )


@dataclass(frozen=True)
class ScoringPolicy:
    default_rule: EquivalenceRule = field(default_factory=EquivalenceRule)
    task_rules: Mapping[str, EquivalenceRule] = field(default_factory=dict)
    exclusions: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    policy_name: str = "exact-first-attempt"

    def __post_init__(self) -> None:
        rules = {require_id(key, "task rule id"): value for key, value in self.task_rules.items()}
        exclusions: dict[str, tuple[int, ...]] = {}
        for key, indexes in self.exclusions.items():
            task_id = require_id(key, "exclusion task id")
            normalized = tuple(sorted(set(int(index) for index in indexes)))
            if any(index < 0 for index in normalized):
                raise ValueError("exclusion indexes must be nonnegative")
            exclusions[task_id] = normalized
        object.__setattr__(self, "task_rules", rules)
        object.__setattr__(self, "exclusions", exclusions)
        if not self.policy_name.strip():
            raise ValueError("policy_name must be non-empty")

    def to_data(self) -> dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "default_rule": self.default_rule.to_data(),
            "task_rules": {key: self.task_rules[key].to_data() for key in sorted(self.task_rules)},
            "exclusions": {key: list(self.exclusions[key]) for key in sorted(self.exclusions)},
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "ScoringPolicy":
        require_fields(data, name="ScoringPolicy", allowed={"policy_name", "default_rule", "task_rules", "exclusions"}, required={"default_rule"})
        rules_raw = data.get("task_rules", {})
        exclusions_raw = data.get("exclusions", {})
        if not isinstance(rules_raw, Mapping) or not isinstance(exclusions_raw, Mapping):
            raise ValueError("task_rules and exclusions must be mappings")
        return cls(
            default_rule=EquivalenceRule.from_data(data["default_rule"]),
            task_rules={str(key): EquivalenceRule.from_data(value) for key, value in rules_raw.items()},
            exclusions={str(key): tuple(int(item) for item in value) for key, value in exclusions_raw.items()},
            policy_name=str(data.get("policy_name", "exact-first-attempt")),
        )


@dataclass(frozen=True)
class PublicTask:
    task_id: str
    instructions: str
    demonstrations: tuple[Demonstration, ...]
    hidden_inputs: tuple[Any, ...]
    output_schema: OutputSchema
    resource_limits: Mapping[str, int | float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", require_id(self.task_id, "task_id"))
        if not self.instructions.strip():
            raise ValueError("instructions must be non-empty")
        demonstrations = tuple(self.demonstrations)
        hidden_inputs = tuple(self.hidden_inputs)
        if not 3 <= len(demonstrations) <= 20:
            raise ValueError("public task requires 3 to 20 demonstrations")
        if not hidden_inputs:
            raise ValueError("public task requires hidden inputs")
        limits = {str(key): value for key, value in self.resource_limits.items()}
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0 for value in limits.values()):
            raise ValueError("resource limits must be positive numbers")
        object.__setattr__(self, "demonstrations", demonstrations)
        object.__setattr__(self, "hidden_inputs", hidden_inputs)
        object.__setattr__(self, "resource_limits", limits)
        require_finite_tree(self.to_data())

    def to_data(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "instructions": self.instructions,
            "demonstrations": [demo.to_data() for demo in self.demonstrations],
            "hidden_inputs": list(self.hidden_inputs),
            "output_schema": self.output_schema.to_data(),
            "resource_limits": dict(sorted(self.resource_limits.items())),
        }

    def to_task_package(self) -> TaskPackage:
        return TaskPackage(self.instructions, self.demonstrations, self.hidden_inputs, self.output_schema, {})

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "PublicTask":
        require_fields(data, name="PublicTask", allowed={"task_id", "instructions", "demonstrations", "hidden_inputs", "output_schema", "resource_limits"}, required={"task_id", "instructions", "demonstrations", "hidden_inputs", "output_schema"})
        demos = data["demonstrations"]
        hidden = data["hidden_inputs"]
        if not isinstance(demos, Sequence) or isinstance(demos, (str, bytes)):
            raise ValueError("demonstrations must be a sequence")
        if not isinstance(hidden, Sequence) or isinstance(hidden, (str, bytes)):
            raise ValueError("hidden_inputs must be a sequence")
        return cls(
            str(data["task_id"]), str(data["instructions"]),
            tuple(_demonstration_from_data(item) for item in demos), tuple(hidden),
            _schema_from_data(data["output_schema"]), dict(data.get("resource_limits", {})),
        )


@dataclass(frozen=True)
class PublicChallengeSuite:
    suite_id: str
    commitment_digest: str
    frozen_core_commit: str
    tasks: tuple[PublicTask, ...]
    public_scoring_specification: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol_version")
        object.__setattr__(self, "suite_id", require_id(self.suite_id, "suite_id"))
        object.__setattr__(self, "commitment_digest", require_digest(self.commitment_digest, "commitment_digest"))
        object.__setattr__(self, "frozen_core_commit", require_commit(self.frozen_core_commit, "frozen_core_commit"))
        tasks = tuple(self.tasks)
        if not tasks:
            raise ValueError("challenge requires at least one task")
        ids = [task.task_id for task in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("public task IDs must be unique")
        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.public_scoring_specification.strip():
            raise ValueError("public scoring specification must be non-empty")
        require_finite_tree(self.to_data())

    def to_data(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "suite_id": self.suite_id,
            "commitment_digest": self.commitment_digest,
            "frozen_core_commit": self.frozen_core_commit,
            "tasks": [task.to_data() for task in self.tasks],
            "public_scoring_specification": self.public_scoring_specification,
            "metadata": dict(self.metadata),
        }

    def binding_data(self) -> dict[str, Any]:
        data = self.to_data()
        data.pop("commitment_digest")
        return data

    @property
    def binding_digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.binding_data()))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "PublicChallengeSuite":
        require_fields(data, name="PublicChallengeSuite", allowed={"protocol_version", "suite_id", "commitment_digest", "frozen_core_commit", "tasks", "public_scoring_specification", "metadata"}, required={"protocol_version", "suite_id", "commitment_digest", "frozen_core_commit", "tasks", "public_scoring_specification"})
        return cls(
            suite_id=str(data["suite_id"]), commitment_digest=str(data["commitment_digest"]),
            frozen_core_commit=str(data["frozen_core_commit"]),
            tasks=tuple(PublicTask.from_data(item) for item in data["tasks"]),
            public_scoring_specification=str(data["public_scoring_specification"]),
            metadata=dict(data.get("metadata", {})), protocol_version=str(data["protocol_version"]),
        )


@dataclass(frozen=True)
class ChallengeCommitment:
    suite_id: str
    public_challenge_digest: str
    private_reveal_digest: str
    scoring_policy_digest: str
    frozen_core_commit: str
    created_at: str
    commitment_digest: str = ZERO_DIGEST
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION: raise ValueError("unsupported protocol_version")
        object.__setattr__(self, "suite_id", require_id(self.suite_id, "suite_id"))
        for name in ("public_challenge_digest", "private_reveal_digest", "scoring_policy_digest", "commitment_digest"):
            object.__setattr__(self, name, require_digest(getattr(self, name), name))
        object.__setattr__(self, "frozen_core_commit", require_commit(self.frozen_core_commit, "frozen_core_commit"))
        object.__setattr__(self, "created_at", require_timestamp(self.created_at, "created_at"))

    def binding_data(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version, "suite_id": self.suite_id,
            "public_challenge_digest": self.public_challenge_digest,
            "private_reveal_digest": self.private_reveal_digest,
            "scoring_policy_digest": self.scoring_policy_digest,
            "frozen_core_commit": self.frozen_core_commit, "created_at": self.created_at,
        }

    def to_data(self) -> dict[str, Any]: return self.binding_data() | {"commitment_digest": self.commitment_digest}
    @property
    def computed_digest(self) -> str: return sha256_hex(canonical_json_bytes(self.binding_data()))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "ChallengeCommitment":
        allowed={"protocol_version","suite_id","public_challenge_digest","private_reveal_digest","scoring_policy_digest","frozen_core_commit","created_at","commitment_digest"}
        require_fields(data,name="ChallengeCommitment",allowed=allowed,required=allowed)
        return cls(**{key:data[key] for key in allowed})


@dataclass(frozen=True)
class CoreIdentity:
    commit: str
    source_files: Mapping[str, str]
    source_digest: str
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION: raise ValueError("unsupported protocol_version")
        object.__setattr__(self, "commit", require_commit(self.commit))
        files = {str(path): require_digest(digest, f"source digest for {path}") for path,digest in self.source_files.items()}
        object.__setattr__(self, "source_files", files)
        object.__setattr__(self, "source_digest", require_digest(self.source_digest, "source_digest"))

    def to_data(self): return {"protocol_version":self.protocol_version,"commit":self.commit,"source_files":dict(sorted(self.source_files.items())),"source_digest":self.source_digest}
    @classmethod
    def from_data(cls,data):
        allowed={"protocol_version","commit","source_files","source_digest"}; require_fields(data,name="CoreIdentity",allowed=allowed,required=allowed)
        return cls(str(data["commit"]),dict(data["source_files"]),str(data["source_digest"]),str(data["protocol_version"]))


@dataclass(frozen=True)
class TaskSubmission:
    task_id: str
    package_digest: str
    solver_digest: str | None
    status: str
    predictions: tuple[Mapping[str, Any], ...]
    prediction_digest: str
    attempt_id: str
    audit_manifest_digest: str
    verification_summary: Mapping[str, Any] = field(default_factory=dict)
    resource_usage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self,"task_id",require_id(self.task_id,"task_id")); object.__setattr__(self,"package_digest",require_digest(self.package_digest,"package_digest"))
        if self.solver_digest is not None: object.__setattr__(self,"solver_digest",require_digest(self.solver_digest,"solver_digest"))
        object.__setattr__(self,"prediction_digest",require_digest(self.prediction_digest,"prediction_digest")); object.__setattr__(self,"audit_manifest_digest",require_digest(self.audit_manifest_digest,"audit_manifest_digest"))
        predictions=tuple(dict(item) for item in self.predictions)
        indexes=[item.get("index") for item in predictions]
        if indexes!=list(range(len(predictions))): raise ValueError("prediction indexes must be contiguous")
        object.__setattr__(self,"predictions",predictions); object.__setattr__(self,"verification_summary",dict(self.verification_summary)); object.__setattr__(self,"resource_usage",dict(self.resource_usage))
        if self.attempt_id!="attempt-0001": raise ValueError("only attempt-0001 is permitted")

    def to_data(self):
        return {"task_id":self.task_id,"package_digest":self.package_digest,"solver_digest":self.solver_digest,"status":self.status,"predictions":[dict(x) for x in self.predictions],"prediction_digest":self.prediction_digest,"attempt_id":self.attempt_id,"audit_manifest_digest":self.audit_manifest_digest,"verification_summary":dict(self.verification_summary),"resource_usage":dict(self.resource_usage)}
    @classmethod
    def from_data(cls,data):
        allowed={"task_id","package_digest","solver_digest","status","predictions","prediction_digest","attempt_id","audit_manifest_digest","verification_summary","resource_usage"}; required=allowed-{"solver_digest","verification_summary","resource_usage"}; require_fields(data,name="TaskSubmission",allowed=allowed,required=required)
        return cls(str(data["task_id"]),str(data["package_digest"]),None if data.get("solver_digest") is None else str(data["solver_digest"]),str(data["status"]),tuple(data["predictions"]),str(data["prediction_digest"]),str(data["attempt_id"]),str(data["audit_manifest_digest"]),dict(data.get("verification_summary",{})),dict(data.get("resource_usage",{})))


@dataclass(frozen=True)
class SubmissionEnvelope:
    suite_id: str
    commitment_digest: str
    public_challenge_digest: str
    frozen_core_commit: str
    core_identity: CoreIdentity
    task_submissions: tuple[TaskSubmission, ...]
    created_at: str
    submission_digest: str = ZERO_DIGEST
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if self.protocol_version!=PROTOCOL_VERSION: raise ValueError("unsupported protocol_version")
        object.__setattr__(self,"suite_id",require_id(self.suite_id,"suite_id")); object.__setattr__(self,"commitment_digest",require_digest(self.commitment_digest,"commitment_digest")); object.__setattr__(self,"public_challenge_digest",require_digest(self.public_challenge_digest,"public_challenge_digest")); object.__setattr__(self,"frozen_core_commit",require_commit(self.frozen_core_commit,"frozen_core_commit")); object.__setattr__(self,"created_at",require_timestamp(self.created_at,"created_at")); object.__setattr__(self,"submission_digest",require_digest(self.submission_digest,"submission_digest"))
        tasks=tuple(self.task_submissions); ids=[t.task_id for t in tasks]
        if len(ids)!=len(set(ids)): raise ValueError("task submission IDs must be unique")
        object.__setattr__(self,"task_submissions",tasks)

    def binding_data(self):
        return {"protocol_version":self.protocol_version,"suite_id":self.suite_id,"commitment_digest":self.commitment_digest,"public_challenge_digest":self.public_challenge_digest,"frozen_core_commit":self.frozen_core_commit,"core_identity":self.core_identity.to_data(),"task_submissions":[x.to_data() for x in self.task_submissions],"created_at":self.created_at}
    def to_data(self): return self.binding_data()|{"submission_digest":self.submission_digest}
    @property
    def computed_digest(self): return sha256_hex(canonical_json_bytes(self.binding_data()))
    @classmethod
    def from_data(cls,data):
        allowed={"protocol_version","suite_id","commitment_digest","public_challenge_digest","frozen_core_commit","core_identity","task_submissions","created_at","submission_digest"}; require_fields(data,name="SubmissionEnvelope",allowed=allowed,required=allowed)
        return cls(str(data["suite_id"]),str(data["commitment_digest"]),str(data["public_challenge_digest"]),str(data["frozen_core_commit"]),CoreIdentity.from_data(data["core_identity"]),tuple(TaskSubmission.from_data(x) for x in data["task_submissions"]),str(data["created_at"]),str(data["submission_digest"]),str(data["protocol_version"]))


@dataclass(frozen=True)
class IndependenceAttestation:
    evaluator_id: str
    evaluator_key: str
    created_at: str
    source_reviewed: bool
    derived_from_repo_tests: bool
    developers_saw_private_material: bool
    external_model_assistance: str | None
    generator_source_digests: tuple[str, ...]
    source_material_digests: tuple[str, ...]
    conflicts_of_interest: tuple[str, ...]
    evaluator_auditor_distinct: bool

    def __post_init__(self):
        object.__setattr__(self,"evaluator_id",require_id(self.evaluator_id,"evaluator_id")); object.__setattr__(self,"created_at",require_timestamp(self.created_at,"attestation created_at"))
        if not self.evaluator_key.strip(): raise ValueError("evaluator_key must be non-empty")
        object.__setattr__(self,"generator_source_digests",tuple(require_digest(x,"generator source digest") for x in self.generator_source_digests)); object.__setattr__(self,"source_material_digests",tuple(require_digest(x,"source material digest") for x in self.source_material_digests)); object.__setattr__(self,"conflicts_of_interest",tuple(str(x) for x in self.conflicts_of_interest))

    def to_data(self):
        return {"evaluator_id":self.evaluator_id,"evaluator_key":self.evaluator_key,"created_at":self.created_at,"source_reviewed":self.source_reviewed,"derived_from_repo_tests":self.derived_from_repo_tests,"developers_saw_private_material":self.developers_saw_private_material,"external_model_assistance":self.external_model_assistance,"generator_source_digests":list(self.generator_source_digests),"source_material_digests":list(self.source_material_digests),"conflicts_of_interest":list(self.conflicts_of_interest),"evaluator_auditor_distinct":self.evaluator_auditor_distinct}
    @classmethod
    def from_data(cls,data):
        allowed={"evaluator_id","evaluator_key","created_at","source_reviewed","derived_from_repo_tests","developers_saw_private_material","external_model_assistance","generator_source_digests","source_material_digests","conflicts_of_interest","evaluator_auditor_distinct"}; require_fields(data,name="IndependenceAttestation",allowed=allowed,required=allowed)
        return cls(str(data["evaluator_id"]),str(data["evaluator_key"]),str(data["created_at"]),bool(data["source_reviewed"]),bool(data["derived_from_repo_tests"]),bool(data["developers_saw_private_material"]),None if data["external_model_assistance"] is None else str(data["external_model_assistance"]),tuple(data["generator_source_digests"]),tuple(data["source_material_digests"]),tuple(data["conflicts_of_interest"]),bool(data["evaluator_auditor_distinct"]))


@dataclass(frozen=True)
class TaskReveal:
    task_id: str
    targets: tuple[Any, ...]
    family_id: str
    generalization_level: GeneralizationLevel
    construction_method: str
    provenance: Mapping[str, Any]
    ambiguity_annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self,"task_id",require_id(self.task_id,"task_id")); object.__setattr__(self,"family_id",require_id(self.family_id,"family_id")); object.__setattr__(self,"targets",tuple(self.targets)); object.__setattr__(self,"provenance",dict(self.provenance)); object.__setattr__(self,"ambiguity_annotations",dict(self.ambiguity_annotations))
        if not self.targets: raise ValueError("task reveal requires targets")
        if not self.construction_method.strip(): raise ValueError("construction_method must be non-empty")
        require_finite_tree(self.to_data())

    def to_data(self): return {"task_id":self.task_id,"targets":list(self.targets),"family_id":self.family_id,"generalization_level":self.generalization_level.value,"construction_method":self.construction_method,"provenance":dict(self.provenance),"ambiguity_annotations":dict(self.ambiguity_annotations)}
    @classmethod
    def from_data(cls,data):
        allowed={"task_id","targets","family_id","generalization_level","construction_method","provenance","ambiguity_annotations"}; required=allowed-{"ambiguity_annotations"}; require_fields(data,name="TaskReveal",allowed=allowed,required=required)
        return cls(str(data["task_id"]),tuple(data["targets"]),str(data["family_id"]),GeneralizationLevel(int(data["generalization_level"])),str(data["construction_method"]),dict(data["provenance"]),dict(data.get("ambiguity_annotations",{})))


@dataclass(frozen=True)
class PrivateReveal:
    suite_id: str
    commitment_digest: str
    nonce: str
    task_reveals: tuple[TaskReveal, ...]
    scoring_policy: ScoringPolicy
    independence_attestation: IndependenceAttestation
    revealed_at: str
    reveal_digest: str = ZERO_DIGEST
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if self.protocol_version!=PROTOCOL_VERSION: raise ValueError("unsupported protocol_version")
        object.__setattr__(self,"suite_id",require_id(self.suite_id,"suite_id")); object.__setattr__(self,"commitment_digest",require_digest(self.commitment_digest,"commitment_digest")); object.__setattr__(self,"reveal_digest",require_digest(self.reveal_digest,"reveal_digest")); object.__setattr__(self,"revealed_at",require_timestamp(self.revealed_at,"revealed_at"))
        nonce=str(self.nonce)
        if len(nonce)<64 or len(nonce)%2 or not re.fullmatch(r"[0-9a-f]+",nonce): raise ValueError("nonce must encode at least 32 random bytes")
        object.__setattr__(self,"nonce",nonce)
        tasks=tuple(self.task_reveals); ids=[x.task_id for x in tasks]
        if len(ids)!=len(set(ids)): raise ValueError("task reveal IDs must be unique")
        object.__setattr__(self,"task_reveals",tasks)

    def binding_data(self):
        return {"protocol_version":self.protocol_version,"suite_id":self.suite_id,"nonce":self.nonce,"task_reveals":[x.to_data() for x in self.task_reveals],"scoring_policy":self.scoring_policy.to_data(),"independence_attestation":self.independence_attestation.to_data(),"revealed_at":self.revealed_at}
    def to_data(self): return self.binding_data()|{"commitment_digest":self.commitment_digest,"reveal_digest":self.reveal_digest}
    @property
    def computed_digest(self): return sha256_hex(canonical_json_bytes(self.binding_data()))
    @classmethod
    def from_data(cls,data):
        allowed={"protocol_version","suite_id","commitment_digest","nonce","task_reveals","scoring_policy","independence_attestation","revealed_at","reveal_digest"}; require_fields(data,name="PrivateReveal",allowed=allowed,required=allowed)
        return cls(str(data["suite_id"]),str(data["commitment_digest"]),str(data["nonce"]),tuple(TaskReveal.from_data(x) for x in data["task_reveals"]),ScoringPolicy.from_data(data["scoring_policy"]),IndependenceAttestation.from_data(data["independence_attestation"]),str(data["revealed_at"]),str(data["reveal_digest"]),str(data["protocol_version"]))
