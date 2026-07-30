from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Any, Mapping, Protocol, Sequence

from .canonical import canonical_json_bytes, sha256_hex
from .induction import CandidateProposal
from .ir import TaskSpec
from .operators import default_registry
from .programs import OperatorProgram


class ExecutableProgram(Protocol):
    def run(self, value: Any) -> Any: ...
    def to_data(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CandidateSolver:
    candidate_id: str
    spec: TaskSpec
    program: ExecutableProgram
    trust_level: str
    description_length: int
    confidence: float = 1.0
    source: str = ""
    measured_runtime_ms: float = 0.0

    def run(self, row: Any) -> Any:
        return self.program.run(row)

    def to_data(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "spec": self.spec.to_data(),
            "program": self.program.to_data(),
            "trust_level": self.trust_level,
            "description_length": self.description_length,
            "confidence": self.confidence,
            "source": self.source,
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))


@dataclass(frozen=True)
class TemplateProgram:
    template: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(f"unsupported template program version: {self.version}")
        if self.template not in {"affine", "graph_query", "keyword_relation", "finite_ordering"}:
            raise ValueError(f"unsupported template: {self.template}")
        object.__setattr__(self, "parameters", dict(self.parameters))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "TemplateProgram":
        allowed = {"kind", "version", "template", "parameters"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown template program fields: {sorted(unknown)}")
        if data.get("kind") != "template":
            raise ValueError("template program kind must be template")
        return cls(
            template=str(data["template"]),
            parameters=data.get("parameters", {}),
            version=int(data.get("version", 1)),
        )

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": "template",
            "version": self.version,
            "template": self.template,
            "parameters": dict(self.parameters),
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))

    def run(self, value: Any) -> Any:
        if self.template == "affine":
            return self.parameters["a"] * value + self.parameters["b"]
        if self.template == "graph_query":
            if not isinstance(value, Mapping):
                raise TypeError("graph query input must be a mapping")
            graph = value.get("graph", value)
            start_field = str(self.parameters.get("start_field", "start"))
            goal_field = str(self.parameters.get("goal_field", "goal"))
            return default_registry().execute(
                str(self.parameters.get("operator", "graph_reachable")),
                graph,
                {"start": value[start_field], "goal": value[goal_field]},
            )
        if self.template == "keyword_relation":
            text = str(value).casefold()
            for rule in self.parameters.get("rules", []):
                if str(rule["token"]).casefold() in text:
                    return rule["label"]
            return self.parameters.get("default")
        if self.template == "finite_ordering":
            return _run_ordering(self.parameters, value)
        raise AssertionError("unreachable template")


@dataclass(frozen=True)
class FixedOrderingProgram:
    entities: tuple[str, ...]
    before: tuple[tuple[str, str], ...] = ()
    adjacent: tuple[tuple[str, str], ...] = ()
    after: tuple[tuple[str, str], ...] = ()
    not_adjacent: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        entities = tuple(str(item) for item in self.entities)
        if len(entities) != len(set(entities)):
            raise ValueError("ordering entities must be unique")
        if not 1 <= len(entities) <= 9:
            raise ValueError("ordering template supports 1 to 9 entities")
        object.__setattr__(self, "entities", entities)
        for field_name in ("before", "adjacent", "after", "not_adjacent"):
            pairs = tuple((str(left), str(right)) for left, right in getattr(self, field_name))
            unknown = {entity for pair in pairs for entity in pair} - set(entities)
            if unknown:
                raise ValueError(f"ordering constraint references unknown entities: {sorted(unknown)}")
            object.__setattr__(self, field_name, pairs)

    def to_data(self) -> dict[str, Any]:
        return {
            "kind": "template",
            "version": 1,
            "template": "finite_ordering",
            "parameters": {
                "entities": list(self.entities),
                "before": [list(pair) for pair in self.before],
                "adjacent": [list(pair) for pair in self.adjacent],
                "after": [list(pair) for pair in self.after],
                "not_adjacent": [list(pair) for pair in self.not_adjacent],
            },
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))

    def run(self, value: Any) -> Any:
        query = value.get("query", "order") if isinstance(value, Mapping) else value
        orders = _solve_orderings(self.entities, self.before, self.adjacent, self.after, self.not_adjacent)
        return _answer_ordering_query(orders, query)


def _constraints_hold(
    order: tuple[str, ...],
    before: Sequence[tuple[str, str]],
    adjacent: Sequence[tuple[str, str]],
    after: Sequence[tuple[str, str]],
    not_adjacent: Sequence[tuple[str, str]],
) -> bool:
    positions = {entity: index for index, entity in enumerate(order)}
    return (
        all(positions[left] < positions[right] for left, right in before)
        and all(abs(positions[left] - positions[right]) == 1 for left, right in adjacent)
        and all(positions[left] > positions[right] for left, right in after)
        and all(abs(positions[left] - positions[right]) != 1 for left, right in not_adjacent)
    )


def _solve_orderings_z3(
    entities: tuple[str, ...],
    before: tuple[tuple[str, str], ...],
    adjacent: tuple[tuple[str, str], ...],
    after: tuple[tuple[str, str], ...],
    not_adjacent: tuple[tuple[str, str], ...],
) -> list[tuple[str, ...]]:
    import z3  # type: ignore[import-not-found]

    positions = {entity: z3.Int(f"p_{index}") for index, entity in enumerate(entities)}
    solver = z3.Solver()
    solver.add(z3.Distinct(*positions.values()))
    for position in positions.values():
        solver.add(position >= 0, position < len(entities))
    for left, right in before:
        solver.add(positions[left] < positions[right])
    for left, right in after:
        solver.add(positions[left] > positions[right])
    for left, right in adjacent:
        solver.add(z3.Abs(positions[left] - positions[right]) == 1)
    for left, right in not_adjacent:
        solver.add(z3.Abs(positions[left] - positions[right]) != 1)
    orders: list[tuple[str, ...]] = []
    while solver.check() == z3.sat:
        model = solver.model()
        order = tuple(sorted(entities, key=lambda entity: model[positions[entity]].as_long()))
        orders.append(order)
        solver.add(z3.Or(*[positions[entity] != model[positions[entity]] for entity in entities]))
        if len(orders) > 50_000:
            raise RuntimeError("ordering solution limit exceeded")
    return sorted(set(orders))


def _solve_orderings(
    entities: tuple[str, ...],
    before: tuple[tuple[str, str], ...] = (),
    adjacent: tuple[tuple[str, str], ...] = (),
    after: tuple[tuple[str, str], ...] = (),
    not_adjacent: tuple[tuple[str, str], ...] = (),
) -> list[tuple[str, ...]]:
    try:
        orders = _solve_orderings_z3(entities, before, adjacent, after, not_adjacent)
    except ImportError:
        orders = [
            order
            for order in permutations(sorted(entities))
            if _constraints_hold(order, before, adjacent, after, not_adjacent)
        ]
    if not orders:
        raise ValueError("ordering constraints are unsatisfiable")
    return sorted(orders)


def _answer_ordering_query(orders: Sequence[tuple[str, ...]], query: Any) -> Any:
    order = orders[0]
    if query == "order":
        return list(order)
    if query == "first":
        return order[0]
    if query == "last":
        return order[-1]
    if isinstance(query, Mapping):
        kind = query.get("type")
        if kind == "position":
            return order.index(str(query["entity"])) + 1
        if kind == "at":
            return order[int(query["position"]) - 1]
        if kind == "before":
            return order.index(str(query["left"])) < order.index(str(query["right"]))
    raise ValueError(f"unsupported ordering query: {query!r}")


def _run_ordering(parameters: Mapping[str, Any], value: Any) -> Any:
    if isinstance(value, Mapping) and "entities" in value:
        program = FixedOrderingProgram(
            entities=tuple(value["entities"]),
            before=tuple(tuple(pair) for pair in value.get("before", ())),
            adjacent=tuple(tuple(pair) for pair in value.get("adjacent", ())),
            after=tuple(tuple(pair) for pair in value.get("after", ())),
            not_adjacent=tuple(tuple(pair) for pair in value.get("not_adjacent", ())),
        )
        return program.run({"query": value.get("query", "order")})
    program = FixedOrderingProgram(
        entities=tuple(parameters["entities"]),
        before=tuple(tuple(pair) for pair in parameters.get("before", ())),
        adjacent=tuple(tuple(pair) for pair in parameters.get("adjacent", ())),
        after=tuple(tuple(pair) for pair in parameters.get("after", ())),
        not_adjacent=tuple(tuple(pair) for pair in parameters.get("not_adjacent", ())),
    )
    return program.run(value)


def synthesize_ordering_solver(
    *,
    entities: tuple[str, ...],
    before: tuple[tuple[str, str], ...] = (),
    adjacent: tuple[tuple[str, str], ...] = (),
    after: tuple[tuple[str, str], ...] = (),
    not_adjacent: tuple[tuple[str, str], ...] = (),
) -> FixedOrderingProgram:
    return FixedOrderingProgram(entities, before, adjacent, after, not_adjacent)


class TemplateSynthesizer:
    def synthesize(self, proposal: CandidateProposal) -> CandidateSolver:
        kind = proposal.program_data.get("kind")
        if kind == "operator_program":
            program: ExecutableProgram = OperatorProgram.from_data(proposal.program_data)
            trust_level = "trusted_operator"
        elif kind == "template":
            program = TemplateProgram.from_data(proposal.program_data)
            trust_level = "template"
        elif kind == "minilang":
            from .minilang import MiniLangProgram

            program = MiniLangProgram.from_data(proposal.program_data)
            trust_level = "minilang"
        else:
            raise ValueError(f"unsupported proposal program kind: {kind}")
        program_data = program.to_data()
        candidate_id = sha256_hex(
            canonical_json_bytes({"proposal_id": proposal.proposal_id, "program": program_data})
        )[:16]
        return CandidateSolver(
            candidate_id=candidate_id,
            spec=proposal.spec,
            program=program,
            trust_level=trust_level,
            description_length=len(canonical_json_bytes(program_data)),
            confidence=proposal.confidence,
            source=proposal.source,
        )
