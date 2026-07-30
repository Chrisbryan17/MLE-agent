from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .canonical import canonical_json_bytes
from .contracts import Demonstration, OutputSchema, TaskPackage
from .ir import Capability
from .programs import OperatorProgram
from .templates import CandidateSolver, TemplateProgram


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    evidence: Mapping[str, Any]
    failure: str | None = None
    executed: bool = True
    nontrivial: bool = False


@dataclass(frozen=True)
class VerificationReport:
    candidate_id: str
    checks: tuple[VerificationCheck, ...]
    demonstration_accuracy: float
    deterministic: bool
    accepted: bool

    @property
    def pass_count(self) -> int:
        return sum(check.executed and check.passed for check in self.checks)

    @property
    def nontrivial_pass_count(self) -> int:
        return sum(check.executed and check.passed and check.nontrivial for check in self.checks)

    def to_data(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "demonstration_accuracy": self.demonstration_accuracy,
            "deterministic": self.deterministic,
            "accepted": self.accepted,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "executed": check.executed,
                    "nontrivial": check.nontrivial,
                    "evidence": dict(check.evidence),
                    "failure": check.failure,
                }
                for check in self.checks
            ],
        }


def _skip(name: str, reason: str, *, nontrivial: bool = True) -> VerificationCheck:
    return VerificationCheck(name, False, {"skipped": reason}, executed=False, nontrivial=nontrivial)


def _schema_accepts(schema: OutputSchema, value: Any) -> bool:
    if value is None:
        return schema.nullable
    kind = schema.kind.casefold()
    if kind in {"inferred", "any", "unknown"}:
        accepted = True
    elif kind in {"integer", "int"}:
        accepted = isinstance(value, int) and not isinstance(value, bool)
    elif kind in {"number", "float"}:
        accepted = isinstance(value, int | float) and not isinstance(value, bool)
    elif kind in {"boolean", "bool"}:
        accepted = isinstance(value, bool)
    elif kind in {"string", "str", "text"}:
        accepted = isinstance(value, str)
    elif kind in {"list", "array", "sequence"}:
        accepted = isinstance(value, list | tuple)
    elif kind in {"map", "mapping", "record", "object"}:
        accepted = isinstance(value, Mapping)
    else:
        accepted = True
    if accepted and schema.enum_values:
        accepted = value in schema.enum_values
    return accepted


def _replay(candidate: CandidateSolver, demonstrations: Sequence[Demonstration]) -> tuple[list[Any], list[str | None]]:
    outputs: list[Any] = []
    errors: list[str | None] = []
    for demo in demonstrations:
        try:
            outputs.append(candidate.run(demo.input))
            errors.append(None)
        except Exception as exc:  # noqa: BLE001 - evidence must capture deterministic candidate failures
            outputs.append(None)
            errors.append(f"{type(exc).__name__}: {exc}")
    return outputs, errors


def _renaming_map(values: Sequence[Any]) -> dict[str, str]:
    strings: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, str):
            strings.add(value)
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if key in {"query", "type", "operator", "directed"}:
                    continue
                collect(item)
        elif isinstance(value, list | tuple):
            for item in value:
                collect(item)

    for value in values:
        collect(value)
    return {value: f"symbol_{index}" for index, value in enumerate(sorted(strings))}


def _rename(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_rename(item, mapping) for item in value]
    if isinstance(value, tuple):
        return tuple(_rename(item, mapping) for item in value)
    if isinstance(value, Mapping):
        return {
            key: item if key in {"query", "type", "operator", "directed"} else _rename(item, mapping)
            for key, item in value.items()
        }
    return value


def _entity_renaming_check(candidate: CandidateSolver, package: TaskPackage) -> VerificationCheck:
    if Capability.CLASSIFY in candidate.spec.capabilities:
        return _skip("entity_renaming", "semantic classification tokens are not alpha-renamable")
    values = [demo.input for demo in package.demonstrations] + [demo.output for demo in package.demonstrations]
    mapping = _renaming_map(values)
    if not mapping:
        return _skip("entity_renaming", "no symbolic values")
    failures: list[int] = []
    errors: list[str] = []
    for index, demo in enumerate(package.demonstrations):
        renamed_input = _rename(demo.input, mapping)
        renamed_output = _rename(demo.output, mapping)
        try:
            actual = candidate.run(renamed_input)
        except Exception as exc:  # noqa: BLE001
            failures.append(index)
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        if actual != renamed_output:
            failures.append(index)
    return VerificationCheck(
        "entity_renaming",
        not failures,
        {"renamed_symbols": len(mapping), "failed_rows": failures, "errors": errors},
        None if not failures else "candidate is not invariant to symbolic renaming",
        nontrivial=True,
    )


def _mutated_program(candidate: CandidateSolver) -> Any | None:
    data = candidate.program.to_data()
    if data.get("kind") == "operator_program":
        steps = [dict(step) for step in data["steps"]]
        for step in steps:
            if step["operator"] in {"sort_records", "sort_values"}:
                arguments = dict(step.get("arguments", {}))
                arguments["descending"] = not bool(arguments.get("descending", False))
                step["arguments"] = arguments
                return OperatorProgram.from_data({**data, "steps": steps})
            if step["operator"] == "filter_compare":
                arguments = dict(step.get("arguments", {}))
                flips = {">=": "<", ">": "<=", "<=": ">", "<": ">=", "==": "!=", "!=": "=="}
                arguments["comparison"] = flips[arguments["comparison"]]
                step["arguments"] = arguments
                return OperatorProgram.from_data({**data, "steps": steps})
    if data.get("kind") == "template" and data.get("template") == "affine":
        parameters = dict(data["parameters"])
        parameters["a"] += 1
        return TemplateProgram.from_data({**data, "parameters": parameters})
    return None


def _mutation_check(candidate: CandidateSolver, package: TaskPackage) -> VerificationCheck:
    mutation = _mutated_program(candidate)
    if mutation is None:
        return _skip("mutation_resistance", "no defined mutation for candidate family")
    distinguished = []
    for index, demo in enumerate(package.demonstrations):
        try:
            if mutation.run(demo.input) != demo.output:
                distinguished.append(index)
        except Exception:  # noqa: BLE001
            distinguished.append(index)
    return VerificationCheck(
        "mutation_resistance",
        bool(distinguished),
        {"distinguished_rows": distinguished},
        None if distinguished else "demonstrations do not distinguish a plausible mutation",
        nontrivial=True,
    )


def _bounded_counterexample_check(candidate: CandidateSolver) -> VerificationCheck:
    data = candidate.program.to_data()
    cases: list[tuple[Any, Any]] = []
    if data.get("kind") == "template" and data.get("template") == "affine":
        a = data["parameters"]["a"]
        b = data["parameters"]["b"]
        cases = [(value, a * value + b) for value in (-11, -3, 0, 7, 19)]
    elif data.get("kind") == "template" and data.get("template") == "finite_ordering":
        cases = [({
            "entities": ["lumen", "mira", "nox"],
            "before": [["lumen", "mira"], ["mira", "nox"]],
            "adjacent": [],
            "query": "last",
        }, "nox")]
    elif data.get("kind") == "template" and data.get("template") == "keyword_relation":
        cases = [
            (f"fresh context {rule['token']} marker", rule["label"])
            for rule in data["parameters"].get("rules", [])
        ]
    elif data.get("kind") == "operator_program":
        first = data["steps"][0]
        operator = first["operator"]
        arguments = first.get("arguments", {})
        if operator == "sort_records":
            field = arguments["field"]
            descending = bool(arguments.get("descending", False))
            if isinstance(field, int):
                value = [["r", 13], ["s", -2], ["t", 5]]
            else:
                value = [{"name": "r", field: 13}, {"name": "s", field: -2}, {"name": "t", field: 5}]
            cases = [(value, sorted(value, key=lambda item: item[field], reverse=descending))]
        elif operator == "sort_values":
            value = [13, -2, 5, 5]
            cases = [(value, sorted(value, reverse=bool(arguments.get("descending", False))))]
        elif operator == "count":
            cases = [([], 0), ([1, 2, 3, 4, 5, 6, 7], 7)]
        elif operator == "sum_numbers":
            cases = [([-5, 0, 12, 3], 10)]
        elif operator == "reverse":
            cases = [([1, 9, 2, 7], [7, 2, 9, 1])]
    if not cases:
        return _skip("bounded_counterexamples", "no independent generator for candidate family")
    failures: list[int] = []
    errors: list[str] = []
    for index, (value, expected) in enumerate(cases):
        try:
            actual = candidate.run(value)
        except Exception as exc:  # noqa: BLE001
            failures.append(index)
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        if actual != expected:
            failures.append(index)
    return VerificationCheck(
        "bounded_counterexamples",
        not failures,
        {"case_count": len(cases), "failed_cases": failures, "errors": errors},
        None if not failures else "candidate failed independently generated cases",
        nontrivial=True,
    )


def verify_candidate(
    candidate: CandidateSolver,
    package: TaskPackage,
    candidate_factory: Callable[[tuple[Demonstration, ...]], CandidateSolver] | None = None,
    alternative_candidates: Sequence[CandidateSolver] = (),
) -> VerificationReport:
    checks: list[VerificationCheck] = []
    outputs, errors = _replay(candidate, package.demonstrations)
    correct = [error is None and output == demo.output for output, error, demo in zip(outputs, errors, package.demonstrations)]
    accuracy = sum(correct) / len(correct)
    checks.append(
        VerificationCheck(
            "demonstration_replay",
            all(correct),
            {"correct": sum(correct), "total": len(correct), "errors": [error for error in errors if error]},
            None if all(correct) else "candidate does not reproduce all demonstrations",
        )
    )

    second_outputs, second_errors = _replay(candidate, package.demonstrations)
    deterministic = outputs == second_outputs and errors == second_errors
    checks.append(
        VerificationCheck(
            "deterministic_replay",
            deterministic,
            {"runs": 2},
            None if deterministic else "candidate outputs differ across identical executions",
        )
    )

    schema_failures = [index for index, output in enumerate(outputs) if errors[index] is None and not _schema_accepts(package.output_schema, output)]
    checks.append(
        VerificationCheck(
            "output_schema",
            not schema_failures,
            {"failed_rows": schema_failures, "kind": package.output_schema.kind},
            None if not schema_failures else "candidate outputs conflict with the output schema",
        )
    )

    if candidate_factory is not None and len(package.demonstrations) >= 4:
        failures: list[int] = []
        for index, omitted in enumerate(package.demonstrations):
            remaining = package.demonstrations[:index] + package.demonstrations[index + 1 :]
            try:
                rebuilt = candidate_factory(remaining)
                if rebuilt.run(omitted.input) != omitted.output:
                    failures.append(index)
            except Exception:  # noqa: BLE001
                failures.append(index)
        checks.append(
            VerificationCheck(
                "leave_one_out",
                not failures,
                {"failed_rows": failures},
                None if not failures else "re-induced candidate failed omitted demonstrations",
                nontrivial=True,
            )
        )
    else:
        checks.append(_skip("leave_one_out", "candidate factory unavailable or fewer than four demonstrations"))

    reorder_outputs, reorder_errors = _replay(candidate, tuple(reversed(package.demonstrations)))
    expected_reversed = [demo.output for demo in reversed(package.demonstrations)]
    reorder_passed = not any(reorder_errors) and reorder_outputs == expected_reversed
    checks.append(
        VerificationCheck(
            "demonstration_reordering",
            reorder_passed,
            {"rows": len(reorder_outputs)},
            None if reorder_passed else "candidate changed under demonstration replay order",
            nontrivial=True,
        )
    )

    checks.append(_entity_renaming_check(candidate, package))

    if not candidate.spec.order_sensitive and any(isinstance(demo.input, list) for demo in package.demonstrations):
        failures = []
        for index, demo in enumerate(package.demonstrations):
            if isinstance(demo.input, list):
                try:
                    if candidate.run(list(reversed(demo.input))) != demo.output:
                        failures.append(index)
                except Exception:  # noqa: BLE001
                    failures.append(index)
        checks.append(
            VerificationCheck(
                "row_order_invariance",
                not failures,
                {"failed_rows": failures},
                None if not failures else "order-insensitive candidate depends on row order",
                nontrivial=True,
            )
        )
    else:
        checks.append(_skip("row_order_invariance", "task specification is order-sensitive or inputs are not lists"))

    checks.append(_mutation_check(candidate, package))

    if alternative_candidates:
        disagreements = []
        probe_inputs = [demo.input for demo in package.demonstrations]
        for alternative in alternative_candidates:
            if alternative.candidate_id == candidate.candidate_id:
                continue
            if any(candidate.run(value) != alternative.run(value) for value in probe_inputs):
                disagreements.append(alternative.candidate_id)
        checks.append(
            VerificationCheck(
                "differential_candidates",
                not disagreements,
                {"disagreements": disagreements},
                None if not disagreements else "verified candidates disagree",
                nontrivial=True,
            )
        )
    else:
        checks.append(_skip("differential_candidates", "no alternative candidates supplied"))

    checks.append(_bounded_counterexample_check(candidate))

    essentials = {"demonstration_replay", "deterministic_replay", "output_schema"}
    essentials_pass = all(check.passed for check in checks if check.name in essentials)
    executed_failures = [check for check in checks if check.executed and not check.passed]
    nontrivial_passes = sum(check.executed and check.passed and check.nontrivial for check in checks)
    accepted = essentials_pass and not executed_failures and nontrivial_passes >= 2
    return VerificationReport(
        candidate_id=candidate.candidate_id,
        checks=tuple(checks),
        demonstration_accuracy=accuracy,
        deterministic=deterministic,
        accepted=accepted,
    )


def output_matches_schema(schema: OutputSchema, value: Any) -> bool:
    """Public schema predicate used after hidden execution."""
    return _schema_accepts(schema, value)
