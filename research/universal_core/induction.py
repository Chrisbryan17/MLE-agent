from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from fractions import Fraction
from numbers import Real
from typing import Any, Callable, Mapping, Protocol, Sequence

from .canonical import canonical_json_bytes, sha256_hex
from .contracts import Demonstration, OutputSchema, TaskPackage
from .ir import Capability, TaskSpec, ValueType
from .operators import default_registry
from .programs import OperatorProgram


@dataclass(frozen=True)
class CandidateProposal:
    spec: TaskSpec
    program_data: Mapping[str, Any]
    source: str
    confidence: float
    rationale: str = ""
    proposal_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposal confidence must be between 0 and 1")
        program_data = dict(self.program_data)
        object.__setattr__(self, "program_data", program_data)
        digest_payload = {
            "spec": self.spec.to_data(),
            "program": program_data,
            "source": self.source,
        }
        object.__setattr__(self, "proposal_id", sha256_hex(canonical_json_bytes(digest_payload))[:16])


class ProposalBackend(Protocol):
    def propose(
        self,
        instructions: str,
        demonstrations: tuple[Demonstration, ...],
        output_schema: OutputSchema,
    ) -> tuple[CandidateProposal, ...]: ...


def build_induction_view(package: TaskPackage) -> dict[str, Any]:
    return {
        "instructions": package.instructions,
        "demonstrations": [demo.to_data() for demo in package.demonstrations],
        "output_schema": package.output_schema.to_data(),
    }


def infer_value_type(value: Any) -> ValueType:
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, int):
        return ValueType.INTEGER
    if isinstance(value, Real):
        return ValueType.NUMBER
    if isinstance(value, str):
        return ValueType.STRING
    if isinstance(value, Mapping):
        if "edges" in value:
            return ValueType.GRAPH
        return ValueType.RECORD
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        if value and all(isinstance(item, Mapping | Sequence) and not isinstance(item, str | bytes) for item in value):
            return ValueType.TABLE
        return ValueType.LIST
    if isinstance(value, set | frozenset):
        return ValueType.SET
    return ValueType.UNKNOWN


def _program(operator: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "kind": "operator_program",
        "version": 1,
        "steps": [
            {
                "operator": operator,
                "source": "$input",
                "target": "$output",
                "arguments": dict(arguments or {}),
            }
        ],
    }


def _pipeline(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kind": "operator_program", "version": 1, "steps": steps}


def _number_data(value: Fraction) -> int | float:
    if value.denominator == 1:
        return value.numerator
    return value.numerator / value.denominator


def _template_run(data: Mapping[str, Any], value: Any) -> Any:
    template = data.get("template")
    parameters = data.get("parameters", {})
    if template == "affine":
        return parameters["a"] * value + parameters["b"]
    if template == "graph_query":
        if not isinstance(value, Mapping):
            raise TypeError("graph query input must be a mapping")
        graph = value.get("graph", value)
        query_args = {"start": value[parameters.get("start_field", "start")], "goal": value[parameters.get("goal_field", "goal")]}
        operator = parameters.get("operator", "graph_reachable")
        return default_registry().execute(operator, graph, query_args)
    if template == "keyword_relation":
        text = str(value).casefold()
        for rule in parameters.get("rules", []):
            if str(rule["token"]).casefold() in text:
                return rule["label"]
        return parameters.get("default")
    raise ValueError(f"unsupported template: {template}")


def evaluate_program_data(program_data: Mapping[str, Any], value: Any) -> Any:
    kind = program_data.get("kind")
    if kind == "operator_program":
        return OperatorProgram.from_data(program_data).run(value, default_registry())
    if kind == "template":
        return _template_run(program_data, value)
    raise ValueError(f"unsupported program kind: {kind}")


def _fits(program_data: Mapping[str, Any], demonstrations: Sequence[Demonstration]) -> bool:
    try:
        return all(evaluate_program_data(program_data, demo.input) == demo.output for demo in demonstrations)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _field_candidates(rows: Sequence[Any]) -> tuple[Any, ...]:
    if not rows:
        return ()
    first = rows[0]
    if isinstance(first, Mapping):
        common = set(first)
        for row in rows[1:]:
            if not isinstance(row, Mapping):
                return ()
            common &= set(row)
        return tuple(sorted(common, key=str))
    if isinstance(first, Sequence) and not isinstance(first, str | bytes):
        lengths = [len(row) for row in rows if isinstance(row, Sequence) and not isinstance(row, str | bytes)]
        if len(lengths) != len(rows) or not lengths:
            return ()
        return tuple(range(min(lengths)))
    return ()


def _extract_field(record: Any, field_name: Any) -> Any:
    return record[field_name]


def _task_spec(
    demonstrations: Sequence[Demonstration],
    capabilities: tuple[Capability, ...],
    objective: str,
    confidence: float,
    *,
    order_sensitive: bool = True,
) -> TaskSpec:
    return TaskSpec(
        input_type=infer_value_type(demonstrations[0].input),
        output_type=infer_value_type(demonstrations[0].output),
        capabilities=capabilities,
        objective=objective,
        confidence=confidence,
        provenance=tuple(range(len(demonstrations))),
        order_sensitive=order_sensitive,
    )


def _proposal(
    demonstrations: Sequence[Demonstration],
    program_data: Mapping[str, Any],
    capabilities: tuple[Capability, ...],
    objective: str,
    confidence: float,
    rationale: str,
) -> CandidateProposal | None:
    if not _fits(program_data, demonstrations):
        return None
    return CandidateProposal(
        spec=_task_spec(demonstrations, capabilities, objective, confidence),
        program_data=program_data,
        source="heuristic",
        confidence=confidence,
        rationale=rationale,
    )


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if len(token) > 1}


class HeuristicProposalBackend:
    def propose(
        self,
        instructions: str,
        demonstrations: tuple[Demonstration, ...],
        output_schema: OutputSchema,
    ) -> tuple[CandidateProposal, ...]:
        del output_schema
        if not demonstrations:
            return ()
        candidates: list[CandidateProposal] = []

        def add(
            data: Mapping[str, Any],
            capabilities: tuple[Capability, ...],
            objective: str,
            confidence: float,
            rationale: str,
        ) -> None:
            proposal = _proposal(demonstrations, data, capabilities, objective, confidence, rationale)
            if proposal is not None:
                candidates.append(proposal)

        add(_program("identity"), (Capability.MAP,), "return the input unchanged", 0.75, "all examples are identity")
        add(_program("reverse"), (Capability.MAP,), "reverse the input sequence", 0.80, "all outputs reverse inputs")
        add(_program("sort_values", {"descending": False}), (Capability.SORT,), "sort values ascending", 0.86, "ascending sort fits")
        add(_program("sort_values", {"descending": True}), (Capability.SORT,), "sort values descending", 0.86, "descending sort fits")
        add(_program("count"), (Capability.COUNT,), "count input items", 0.88, "collection lengths fit")
        add(_program("sum_numbers"), (Capability.AGGREGATE,), "sum numeric input values", 0.88, "numeric sums fit")
        add(_program("min_value"), (Capability.AGGREGATE,), "return minimum input value", 0.84, "minimum values fit")
        add(_program("max_value"), (Capability.AGGREGATE,), "return maximum input value", 0.84, "maximum values fit")

        table_inputs = [demo.input for demo in demonstrations]
        if all(isinstance(value, Sequence) and not isinstance(value, str | bytes) for value in table_inputs):
            all_rows = [row for table in table_inputs for row in table]
            for field_name in _field_candidates(all_rows):
                for descending in (False, True):
                    add(
                        _program("sort_records", {"field": field_name, "descending": descending}),
                        (Capability.SORT, Capability.PROJECT),
                        f"sort records by field {field_name!r} {'descending' if descending else 'ascending'}",
                        0.92,
                        "record-field sort fits every demonstration",
                    )
                add(
                    _program("project_field", {"field": field_name}),
                    (Capability.PROJECT,),
                    f"project record field {field_name!r}",
                    0.86,
                    "field projection fits every demonstration",
                )

            scalar_outputs = all(not isinstance(demo.output, Sequence) or isinstance(demo.output, str | bytes) for demo in demonstrations)
            if scalar_outputs and all_rows:
                fields = _field_candidates(all_rows)
                comparisons = ("==", "!=", "<", "<=", ">", ">=")
                for predicate_field in fields:
                    observed = sorted({_extract_field(row, predicate_field) for row in all_rows}, key=repr)
                    for comparison in comparisons:
                        for threshold in observed:
                            filter_step = {
                                "operator": "filter_compare",
                                "source": "$input",
                                "target": "filtered",
                                "arguments": {"field": predicate_field, "comparison": comparison, "value": threshold},
                            }
                            add(
                                _pipeline([
                                    filter_step,
                                    {"operator": "count", "source": "filtered", "target": "$output", "arguments": {}},
                                ]),
                                (Capability.FILTER, Capability.COUNT),
                                f"filter field {predicate_field!r} {comparison} {threshold!r} then count",
                                0.72,
                                "filter/count parameters fit demonstrations",
                            )
                            for value_field in fields:
                                add(
                                    _pipeline([
                                        filter_step,
                                        {"operator": "project_field", "source": "filtered", "target": "values", "arguments": {"field": value_field}},
                                        {"operator": "sum_numbers", "source": "values", "target": "$output", "arguments": {}},
                                    ]),
                                    (Capability.FILTER, Capability.PROJECT, Capability.AGGREGATE),
                                    f"filter then sum field {value_field!r}",
                                    0.70,
                                    "filter/sum parameters fit demonstrations",
                                )

        numeric_pairs = [
            (Fraction(demo.input), Fraction(demo.output))
            for demo in demonstrations
            if isinstance(demo.input, Real) and not isinstance(demo.input, bool)
            and isinstance(demo.output, Real) and not isinstance(demo.output, bool)
        ]
        if len(numeric_pairs) == len(demonstrations):
            distinct_pair = next(
                ((x1, y1, x2, y2) for x1, y1 in numeric_pairs for x2, y2 in numeric_pairs if x1 != x2),
                None,
            )
            if distinct_pair is not None:
                x1, y1, x2, y2 = distinct_pair
                a = (y2 - y1) / (x2 - x1)
                b = y1 - a * x1
                data = {
                    "kind": "template",
                    "version": 1,
                    "template": "affine",
                    "parameters": {"a": _number_data(a), "b": _number_data(b)},
                }
                add(data, (Capability.EVALUATE_EXPRESSION,), "apply affine transform a*x+b", 0.94, "unique affine relation fits all points")

        if all(isinstance(demo.input, Mapping) for demo in demonstrations):
            for operator in ("graph_reachable", "shortest_path_length"):
                data = {
                    "kind": "template",
                    "version": 1,
                    "template": "graph_query",
                    "parameters": {"operator": operator, "start_field": "start", "goal_field": "goal"},
                }
                add(data, (Capability.TRAVERSE_GRAPH, Capability.COMPUTE_PATH), f"answer {operator} query", 0.90, "graph query template fits")

        if all(isinstance(demo.input, str) and isinstance(demo.output, str) for demo in demonstrations):
            labels = sorted({demo.output for demo in demonstrations})
            rules: list[dict[str, str]] = []
            valid = len(labels) >= 2
            for label in labels:
                own = [_tokenize(demo.input) for demo in demonstrations if demo.output == label]
                other = set().union(*[_tokenize(demo.input) for demo in demonstrations if demo.output != label])
                shared = set.intersection(*own) if own else set()
                discriminative = sorted(shared - other, key=lambda token: (len(token), token))
                if not discriminative:
                    valid = False
                    break
                rules.append({"token": discriminative[0], "label": label})
            if valid:
                data = {
                    "kind": "template",
                    "version": 1,
                    "template": "keyword_relation",
                    "parameters": {"rules": rules, "default": None},
                }
                add(data, (Capability.CLASSIFY, Capability.EXTRACT), "classify by discriminative relation tokens", 0.76, "shared label-specific tokens fit")

        instruction_words = _tokenize(instructions)
        for index, proposal in enumerate(candidates):
            boost = 0.03 if any(capability.value.casefold() in instruction_words for capability in proposal.spec.capabilities) else 0.0
            if boost:
                candidates[index] = CandidateProposal(
                    proposal.spec,
                    proposal.program_data,
                    proposal.source,
                    min(1.0, proposal.confidence + boost),
                    proposal.rationale,
                )

        unique: dict[bytes, CandidateProposal] = {}
        for candidate in candidates:
            key = canonical_json_bytes({"spec": candidate.spec.to_data(), "program": candidate.program_data})
            unique[key] = candidate
        return tuple(sorted(unique.values(), key=lambda item: (-item.confidence, item.proposal_id)))


class JsonProposalBackend:
    def __init__(self, complete: Callable[[str], str]) -> None:
        self._complete = complete

    def _prompt(
        self,
        instructions: str,
        demonstrations: tuple[Demonstration, ...],
        output_schema: OutputSchema,
    ) -> str:
        return json.dumps(
            {
                "instructions": instructions,
                "demonstrations": [demo.to_data() for demo in demonstrations],
                "output_schema": output_schema.to_data(),
                "allowed_operators": default_registry().catalog(),
                "allowed_program_kinds": ["operator_program", "template", "minilang"],
                "required_response": {"proposals": [{"spec": {}, "program": {}, "confidence": 0.0}]},
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    @staticmethod
    def _parse_spec(data: Any) -> TaskSpec:
        if not isinstance(data, Mapping):
            raise ValueError("proposal schema requires a spec mapping")
        allowed = {"input_type", "output_type", "capabilities", "objective", "order_sensitive", "confidence"}
        unknown = set(data) - allowed
        if unknown or "input_type" not in data or "output_type" not in data or "capabilities" not in data:
            raise ValueError("proposal schema contains invalid spec fields")
        try:
            return TaskSpec(
                input_type=ValueType(str(data["input_type"])),
                output_type=ValueType(str(data["output_type"])),
                capabilities=tuple(Capability(str(item)) for item in data["capabilities"]),
                objective=str(data.get("objective", "")),
                order_sensitive=bool(data.get("order_sensitive", True)),
                confidence=float(data.get("confidence", 1.0)),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("proposal schema contains invalid typed spec") from exc

    @staticmethod
    def _validate_program(data: Any) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise ValueError("proposal schema requires a program mapping")
        program = dict(data)
        kind = program.get("kind")
        if kind == "operator_program":
            parsed = OperatorProgram.from_data(program)
            registry = default_registry()
            for step in parsed.steps:
                try:
                    registry.get(step.operator)
                except KeyError as exc:
                    raise ValueError(str(exc).strip("'")) from exc
            return parsed.to_data()
        if kind == "template":
            allowed = {"kind", "version", "template", "parameters"}
            if set(program) - allowed or program.get("template") not in {"affine", "graph_query", "keyword_relation"}:
                raise ValueError("proposal schema contains invalid template")
            return program
        if kind == "minilang":
            return program
        raise ValueError("proposal schema contains invalid program kind")

    def propose(
        self,
        instructions: str,
        demonstrations: tuple[Demonstration, ...],
        output_schema: OutputSchema,
    ) -> tuple[CandidateProposal, ...]:
        raw = self._complete(self._prompt(instructions, demonstrations, output_schema))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("proposal schema is not valid JSON") from exc
        if not isinstance(payload, Mapping) or set(payload) != {"proposals"} or not isinstance(payload["proposals"], list):
            raise ValueError("proposal schema requires exactly a proposals list")
        proposals: list[CandidateProposal] = []
        for item in payload["proposals"]:
            if not isinstance(item, Mapping) or not {"spec", "program", "confidence"} <= set(item) or set(item) - {"spec", "program", "confidence", "rationale"}:
                raise ValueError("proposal schema contains invalid proposal fields")
            spec = self._parse_spec(item["spec"])
            program = self._validate_program(item["program"])
            if not _fits(program, demonstrations):
                continue
            proposals.append(
                CandidateProposal(
                    spec=spec,
                    program_data=program,
                    source="json_backend",
                    confidence=float(item["confidence"]),
                    rationale=str(item.get("rationale", "")),
                )
            )
        return tuple(sorted(proposals, key=lambda item: (-item.confidence, item.proposal_id)))
