from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from numbers import Real
import re
from typing import Any, Iterable, Mapping, Sequence

from .atoms import AtomPool, derive_atoms
from .fibers import FiberSchema
from .program import Program
from .types import SearchConfig


def _demo_parts(item: Any) -> tuple[Any, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return item.input, item.output
    if isinstance(item, Mapping):
        return item["input"], item["output"]
    raise TypeError("demonstration must provide input and output")


def _fits(program: Program, demos: Sequence[Any]) -> bool:
    try:
        return all(program.run(_demo_parts(item)[0]) == _demo_parts(item)[1] for item in demos)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, NotImplementedError):
        return False


def _common_fields(rows: Sequence[Any]) -> tuple[str, ...]:
    if not rows or not all(isinstance(item, Mapping) for item in rows):
        return ()
    names = set(str(key) for key in rows[0])
    for row in rows[1:]:
        names &= {str(key) for key in row}
    return tuple(sorted(names))


def _numeric(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _number_data(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


@dataclass(frozen=True)
class GrammarRule:
    name: str
    program: Program
    depth: int
    provenance: tuple[int, ...] = ()


@dataclass(frozen=True)
class TaskGrammar:
    instructions: str
    demonstrations: tuple[Any, ...]
    atoms: AtomPool
    programs: tuple[Program, ...]
    source_schema: FiberSchema
    target_schema: FiberSchema
    config: SearchConfig
    version: int = 1

    @property
    def sample_input(self) -> Any:
        return _demo_parts(self.demonstrations[0])[0]

    def depth(self, limit: int) -> tuple[Program, ...]:
        return tuple(item for item in self.programs if item.cost <= limit + 1)

    def can_compose(self, left: Program, right: Program) -> bool:
        try:
            middle = left.run(self.sample_input)
            right.run(middle)
            return True
        except (KeyError, TypeError, ValueError, IndexError, NotImplementedError):
            return False


def _add(candidates: dict[str, Program], data: Mapping[str, Any]) -> None:
    try:
        program = Program.parse(data)
    except (KeyError, TypeError, ValueError):
        return
    candidates.setdefault(program.digest, program)


def _affine_candidate(demos: Sequence[Any]) -> Mapping[str, Any] | None:
    pairs = [(_demo_parts(item)[0], _demo_parts(item)[1]) for item in demos]
    if not pairs or not all(_numeric(x) and _numeric(y) for x, y in pairs):
        return None
    distinct = next(((x1, y1, x2, y2) for x1, y1 in pairs for x2, y2 in pairs if x1 != x2), None)
    if distinct is None:
        return None
    x1, y1, x2, y2 = (Fraction(str(item)) for item in distinct)
    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    data = {"kind": "affine", "a": _number_data(a), "b": _number_data(b)}
    program = Program.parse(data)
    return data if _fits(program, demos) else None


def _token_candidate(instructions: str, demos: Sequence[Any], atoms: AtomPool) -> Mapping[str, Any] | None:
    pairs = list(atoms.hints.label_pairs)
    if pairs:
        data = {"kind": "token_map", "mapping": dict(pairs)}
        return data if _fits(Program.parse(data), demos) else None
    if not all(isinstance(_demo_parts(item)[0], str) and isinstance(_demo_parts(item)[1], str) for item in demos):
        return None
    by_label: dict[str, list[set[str]]] = {}
    for item in demos:
        text, label = _demo_parts(item)
        by_label.setdefault(label, []).append(set(text.split()))
    mapping: dict[str, str] = {}
    all_text = {label: set().union(*sets) for label, sets in by_label.items()}
    for label, sets in by_label.items():
        common = set.intersection(*sets)
        others = set().union(*(tokens for other, tokens in all_text.items() if other != label))
        unique = sorted(common - others)
        if not unique:
            return None
        mapping[unique[0]] = label
    data = {"kind": "token_map", "mapping": mapping}
    return data if _fits(Program.parse(data), demos) else None



def _add_if_fits(candidates: dict[str, Program], data: Mapping[str, Any], demos: Sequence[Any]) -> None:
    try:
        program = Program.parse(data)
    except (KeyError, TypeError, ValueError):
        return
    if _fits(program, demos):
        candidates.setdefault(program.digest, program)


def _priority_data(instructions: str, demos: Sequence[Any]) -> Mapping[str, Any] | None:
    lowered = instructions.casefold()
    labels = {str(_demo_parts(item)[1]) for item in demos}
    return_pair = re.search(
        r"return\s+([a-z0-9_-]+)\s+or\s+([a-z0-9_-]+)",
        lowered,
    )
    if return_pair:
        labels.update(item.upper() for item in return_pair.groups())
    ordered_labels = sorted(labels)
    allow_label = next((item for item in ordered_labels if item.casefold().startswith("allow")), None)
    deny_label = next((item for item in ordered_labels if item.casefold().startswith("deny")), None)
    if allow_label is None or deny_label is None:
        return None
    rules: list[dict[str, Any]] = []
    emergency = re.search(
        r"during a\s+([a-z_][a-z0-9_]*),\s*(allow|deny)\s+unless\s+([a-z_][a-z0-9_]*)\s+is\s+true",
        lowered,
    )
    if emergency:
        field, action, exception = emergency.groups()
        rules.append({
            "condition": {
                "op": "and",
                "terms": [
                    {"field": field, "equals": True},
                    {"op": "not", "term": {"field": exception, "equals": True}},
                ],
            },
            "value": allow_label if action == "allow" else deny_label,
        })
    for left, right, action in re.findall(
        r"([a-z_][a-z0-9_]*)\s+together with\s+([a-z_][a-z0-9_]*)\s+(allows|denies)",
        lowered,
    ):
        rules.append({
            "condition": {
                "op": "and",
                "terms": [
                    {"field": left, "equals": True},
                    {"field": right, "equals": True},
                ],
            },
            "value": allow_label if action == "allows" else deny_label,
        })
    for left, one, two, action in re.findall(
        r"([a-z_][a-z0-9_]*)\s+together with\s+either\s+([a-z_][a-z0-9_]*)\s+or\s+([a-z_][a-z0-9_]*)\s+(allows|denies)",
        lowered,
    ):
        rules.append({
            "condition": {
                "op": "and",
                "terms": [
                    {"field": left, "equals": True},
                    {
                        "op": "or",
                        "terms": [
                            {"field": one, "equals": True},
                            {"field": two, "equals": True},
                        ],
                    },
                ],
            },
            "value": allow_label if action == "allows" else deny_label,
        })
    if not rules:
        return None
    default = deny_label if "remaining cases deny" in lowered else allow_label
    return {"kind": "priority_rules", "rules": rules, "default": default}


def _state_fold_candidates(instructions: str, demos: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    triples = re.findall(
        r"([a-z0-9_-]+)\s*\+\s*([a-z0-9_-]+)\s*(?:->|→)\s*([a-z0-9_-]+)",
        instructions.casefold(),
    )
    if not triples:
        return ()
    inputs = [_demo_parts(item)[0] for item in demos]
    outputs = [_demo_parts(item)[1] for item in demos]
    if not inputs or not all(isinstance(item, Mapping) for item in inputs):
        return ()
    fields = _common_fields(inputs)
    sequence_fields = [
        field
        for field in fields
        if all(
            isinstance(item[field], Sequence)
            and not isinstance(item[field], (str, bytes, bytearray))
            for item in inputs
        )
    ]
    state_fields = [
        field
        for field in fields
        if field not in sequence_fields and all(type(item[field]) is type(outputs[index]) for index, item in enumerate(inputs))
    ]
    observed = [*outputs]
    for item in inputs:
        observed.extend(item[field] for field in state_fields)
        for field in sequence_fields:
            observed.extend(item[field])
    by_token = {str(item).casefold(): item for item in observed}
    transitions = [
        {
            "state": by_token.get(state, state),
            "action": by_token.get(action, action),
            "next": by_token.get(nxt, nxt),
        }
        for state, action, nxt in triples
    ]
    candidates: list[Mapping[str, Any]] = []
    for state_field in state_fields:
        for actions_field in sequence_fields:
            data = {
                "kind": "state_fold",
                "state_field": state_field,
                "actions_field": actions_field,
                "transitions": transitions,
            }
            try:
                program = Program.parse(data)
            except (TypeError, ValueError):
                continue
            if _fits(program, demos):
                candidates.append(data)
    return tuple(candidates)



def _stack_rewrite_candidates(instructions: str, demos: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    lowered = instructions.casefold()
    if "stack" not in lowered or "rewrite" not in lowered:
        return ()
    rule_block = re.search(r"\brules?\s*:\s*(.+?)(?:\breturn\b|$)", instructions, re.IGNORECASE | re.DOTALL)
    if rule_block is None:
        return ()
    raw_rules: list[tuple[list[str], list[str]]] = []
    for clause in rule_block.group(1).split(";"):
        match = re.fullmatch(r"\s*(.+?)\s*(?:->|→)\s*(.*?)\s*\.?\s*", clause)
        if match is None:
            continue
        left_text, right_text = match.groups()
        left = left_text.split()
        if not left:
            continue
        right = [] if right_text.casefold() in {"", "empty", "epsilon", "ε"} else right_text.split()
        raw_rules.append((left, right))
    if not raw_rules:
        return ()
    if any(len(right) >= len(left) for left, right in raw_rules):
        return ()

    inputs = [_demo_parts(item)[0] for item in demos]
    outputs = [_demo_parts(item)[1] for item in demos]
    if not inputs or not all(isinstance(item, Mapping) for item in inputs):
        return ()
    fields = _common_fields(inputs)
    candidates: list[Mapping[str, Any]] = []
    for field in fields:
        values = [item[field] for item in inputs]
        modes: tuple[str, ...]
        if all(isinstance(value, str) for value in values) and all(isinstance(value, str) for value in outputs):
            modes = ("characters", "words")
        elif all(
            isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
            for value in values
        ) and all(
            isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
            for value in outputs
        ):
            modes = ("items",)
        else:
            continue

        for mode in modes:
            observed: list[Any] = []
            if mode == "characters":
                for value in [*values, *outputs]:
                    observed.extend(value)
            elif mode == "words":
                for value in [*values, *outputs]:
                    observed.extend(value.split())
            else:
                for value in [*values, *outputs]:
                    observed.extend(value)
            by_token = {str(item).casefold(): item for item in observed}
            rules = [
                {
                    "left": [by_token.get(token.casefold(), token) for token in left],
                    "right": [by_token.get(token.casefold(), token) for token in right],
                }
                for left, right in raw_rules
            ]
            data = {
                "kind": "stack_rewrite",
                "sequence_field": field,
                "token_mode": mode,
                "rules": rules,
            }
            try:
                program = Program.parse(data)
            except (TypeError, ValueError):
                continue
            if _fits(program, demos):
                candidates.append(data)
    return tuple(candidates)


def _weighted_vote_veto_candidates(instructions: str, demos: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    lowered = instructions.casefold()
    if "weighted vote" not in lowered or "veto" not in lowered:
        return ()
    inputs = [_demo_parts(item)[0] for item in demos]
    if not inputs or not all(isinstance(item, Mapping) for item in inputs):
        return ()

    threshold_match = re.search(r"minimum score\s+(-?\d+(?:\.\d+)?)", instructions, re.IGNORECASE)
    threshold = _number_data(Fraction(threshold_match.group(1))) if threshold_match else 0
    default_match = re.search(r"otherwise return\s+([a-z0-9_-]+)", instructions, re.IGNORECASE)
    if default_match is None:
        return ()
    default = default_match.group(1)
    if "lexicograph" in lowered:
        tie_policy = "lexicographic"
    elif "tie" in lowered and "first" in lowered:
        tie_policy = "first"
    elif "tie" in lowered and "error" in lowered:
        tie_policy = "error"
    else:
        tie_policy = "lexicographic"

    def named(fields: tuple[str, ...], names: tuple[str, ...]) -> str | None:
        exact = next((field for field in fields if field.casefold() in names), None)
        if exact is not None:
            return exact
        return next((field for field in fields if any(name in field.casefold() for name in names)), None)

    candidates: list[Mapping[str, Any]] = []
    sequence_fields = [
        field
        for field in _common_fields(inputs)
        if all(
            isinstance(item[field], Sequence)
            and not isinstance(item[field], (str, bytes, bytearray))
            for item in inputs
        )
    ]
    for ballots_field in sequence_fields:
        rows = [row for item in inputs for row in item[ballots_field]]
        fields = _common_fields(rows)
        if not fields:
            continue
        choice_field = named(fields, ("option", "choice", "candidate", "proposal"))
        weight_field = named(fields, ("weight", "power", "points", "strength"))
        support_field = named(fields, ("support", "approve", "approval", "vote", "position"))
        veto_field = named(fields, ("veto", "block", "blocked"))
        if None in {choice_field, weight_field, support_field, veto_field}:
            continue
        data = {
            "kind": "weighted_vote_veto",
            "ballots_field": ballots_field,
            "choice_field": choice_field,
            "weight_field": weight_field,
            "support_field": support_field,
            "veto_field": veto_field,
            "threshold": threshold,
            "tie_policy": tie_policy,
            "default": default,
        }
        try:
            program = Program.parse(data)
        except (TypeError, ValueError):
            continue
        if _fits(program, demos):
            candidates.append(data)
    return tuple(candidates)


def _ray_first_hit_candidates(instructions: str, demos: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    lowered = instructions.casefold()
    if "ray" not in lowered or "origin" not in lowered or "direction" not in lowered:
        return ()
    if "box" not in lowered and "axis-aligned" not in lowered:
        return ()
    inputs = [_demo_parts(item)[0] for item in demos]
    if not inputs or not all(isinstance(item, Mapping) for item in inputs):
        return ()

    default_match = re.search(r"otherwise return\s+([a-z0-9_-]+)", instructions, re.IGNORECASE)
    if default_match is None:
        return ()
    default = default_match.group(1)
    if "lexicograph" in lowered:
        tie_policy = "lexicographic"
    elif "tie" in lowered and "first" in lowered:
        tie_policy = "first"
    elif "tie" in lowered and "error" in lowered:
        tie_policy = "error"
    else:
        tie_policy = "lexicographic"

    def named(fields: Sequence[str], names: tuple[str, ...]) -> str | None:
        exact = next((field for field in fields if field.casefold() in names), None)
        if exact is not None:
            return exact
        return next((field for field in fields if any(name in field.casefold() for name in names)), None)

    fields = _common_fields(inputs)
    origin_field = named(fields, ("origin", "source", "start"))
    direction_field = named(fields, ("direction", "dir", "vector"))
    if origin_field is None or direction_field is None or origin_field == direction_field:
        return ()

    object_fields = [
        field
        for field in fields
        if all(
            isinstance(item[field], Sequence)
            and not isinstance(item[field], (str, bytes, bytearray))
            and item[field]
            and all(isinstance(row, Mapping) for row in item[field])
            for item in inputs
        )
    ]
    candidates: list[Mapping[str, Any]] = []
    for objects_field in object_fields:
        rows = [row for item in inputs for row in item[objects_field]]
        nested = _common_fields(rows)
        id_field = named(nested, ("id", "name", "object", "label"))
        min_field = named(nested, ("min", "minimum", "lower", "low"))
        max_field = named(nested, ("max", "maximum", "upper", "high"))
        if None in {id_field, min_field, max_field}:
            continue
        data = {
            "kind": "ray_first_hit",
            "origin_field": origin_field,
            "direction_field": direction_field,
            "objects_field": objects_field,
            "id_field": id_field,
            "min_field": min_field,
            "max_field": max_field,
            "tie_policy": tie_policy,
            "default": default,
        }
        try:
            program = Program.parse(data)
        except (TypeError, ValueError):
            continue
        if _fits(program, demos):
            candidates.append(data)
    return tuple(candidates)



def _distinct_slot_match_candidates(instructions: str, demos: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    lowered = instructions.casefold()
    if "distinct" not in lowered or "slot" not in lowered:
        return ()
    if "assign" not in lowered and "matching" not in lowered:
        return ()
    inputs = [_demo_parts(item)[0] for item in demos]
    outputs = [_demo_parts(item)[1] for item in demos]
    if not inputs or not all(isinstance(item, Mapping) for item in inputs):
        return ()

    success_match = re.search(r"return\s+([a-z0-9_-]+)\s+if", instructions, re.IGNORECASE)
    failure_match = re.search(r"otherwise\s+return\s+([a-z0-9_-]+)", instructions, re.IGNORECASE)
    if success_match is None or failure_match is None:
        return ()
    by_label = {str(item).casefold(): item for item in outputs}
    success = by_label.get(success_match.group(1).casefold(), success_match.group(1))
    failure = by_label.get(failure_match.group(1).casefold(), failure_match.group(1))

    def named(fields: Sequence[str], names: tuple[str, ...]) -> str | None:
        exact = next((field for field in fields if field.casefold() in names), None)
        if exact is not None:
            return exact
        return next((field for field in fields if any(name in field.casefold() for name in names)), None)

    candidates: list[Mapping[str, Any]] = []
    for items_field in _common_fields(inputs):
        if not all(
            isinstance(item[items_field], Sequence)
            and not isinstance(item[items_field], (str, bytes, bytearray))
            and item[items_field]
            and all(isinstance(row, Mapping) for row in item[items_field])
            for item in inputs
        ):
            continue
        rows = [row for item in inputs for row in item[items_field]]
        fields = _common_fields(rows)
        id_field = named(fields, ("id", "item", "name", "label"))
        slots_field = named(fields, ("slots", "slot", "allowed", "options", "choices"))
        if id_field is None or slots_field is None or id_field == slots_field:
            continue
        data = {
            "kind": "distinct_slot_match",
            "items_field": items_field,
            "id_field": id_field,
            "slots_field": slots_field,
            "success": success,
            "failure": failure,
        }
        try:
            program = Program.parse(data)
        except (TypeError, ValueError):
            continue
        if _fits(program, demos):
            candidates.append(data)
    return tuple(candidates)

def _grid_data(instructions: str, inputs: Sequence[Any]) -> Mapping[str, Any] | None:
    lowered = instructions.casefold()
    if "orthogon" not in lowered or "jump" not in lowered or "count" not in lowered:
        return None
    first = inputs[0]
    if not isinstance(first, Mapping):
        return None
    board_field = next((str(key) for key, value in first.items() if isinstance(value, Sequence) and value and all(isinstance(row, str) for row in value)), None)
    actor_field = next((str(key) for key, value in first.items() if isinstance(value, str)), None)
    if board_field is None or actor_field is None:
        return None
    return {
        "kind": "grid_pattern_count",
        "board_field": board_field,
        "actor_field": actor_field,
        "empty": ".",
        "directions": [[1, 0], [-1, 0], [0, 1], [0, -1]],
        "jump": 2,
    }


def _resource_data(instructions: str, inputs: Sequence[Any]) -> Mapping[str, Any] | None:
    lowered = instructions.casefold()
    if "non-preemptive" not in lowered or "precedence" not in lowered or "completion time" not in lowered:
        return None
    first = inputs[0]
    if not isinstance(first, Mapping):
        return None
    jobs_field = next((str(key) for key, value in first.items() if isinstance(value, Sequence) and value and all(isinstance(item, Mapping) for item in value)), None)
    precedence_field = next((str(key) for key, value in first.items() if isinstance(value, Sequence) and (not value or all(isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) == 2 for item in value))), None)
    if jobs_field is None or precedence_field is None:
        return None
    jobs = first[jobs_field]
    fields = _common_fields(jobs)
    id_field = next((field for field in fields if field.casefold() in {"id", "name", "job"}), None)
    duration_field = next((field for field in fields if "duration" in field.casefold() or "time" in field.casefold()), None)
    resource_field = next((field for field in fields if "machine" in field.casefold() or "resource" in field.casefold()), None)
    if id_field is None or duration_field is None or resource_field is None:
        return None
    return {
        "kind": "resource_makespan",
        "jobs_field": jobs_field,
        "precedence_field": precedence_field,
        "id_field": id_field,
        "duration_field": duration_field,
        "resource_field": resource_field,
    }

def build_task_grammar(
    instructions: str,
    demonstrations: Iterable[Any],
    config: SearchConfig,
) -> TaskGrammar:
    demos = tuple(demonstrations)
    if not demos:
        raise ValueError("at least one demonstration is required")
    atoms = derive_atoms(instructions, demos)
    first_input, first_output = _demo_parts(demos[0])
    candidates: dict[str, Program] = {}

    _add(candidates, {"kind": "input"})
    affine = _affine_candidate(demos)
    if affine is not None:
        _add(candidates, affine)

    token_data = _token_candidate(instructions, demos, atoms)
    if token_data is not None:
        _add(candidates, token_data)

    inputs = [_demo_parts(item)[0] for item in demos]

    if atoms.hints.cycle and all(isinstance(value, Mapping) for value in inputs):
        first_map = inputs[0]
        terms = []
        for field in sorted(first_map):
            observed = first_map[field]
            mode = "cycle" if isinstance(observed, str) and observed in atoms.hints.cycle else "number"
            terms.append({
                "field": str(field),
                "coefficient": int(atoms.hints.coefficients.get(str(field), 1)),
                "mode": mode,
            })
        _add_if_fits(candidates, {
            "kind": "modular_symbol",
            "cycle": list(atoms.hints.cycle),
            "terms": terms,
            "modulus": atoms.hints.modulus or len(atoms.hints.cycle),
        }, demos)

    for state_fold in _state_fold_candidates(instructions, demos):
        _add_if_fits(candidates, state_fold, demos)

    for stack_rewrite in _stack_rewrite_candidates(instructions, demos):
        _add_if_fits(candidates, stack_rewrite, demos)

    for weighted_vote in _weighted_vote_veto_candidates(instructions, demos):
        _add_if_fits(candidates, weighted_vote, demos)

    for ray_first_hit in _ray_first_hit_candidates(instructions, demos):
        _add_if_fits(candidates, ray_first_hit, demos)

    for matching in _distinct_slot_match_candidates(instructions, demos):
        _add_if_fits(candidates, matching, demos)

    priority = _priority_data(instructions, demos)
    if priority is not None:
        _add_if_fits(candidates, priority, demos)
    grid = _grid_data(instructions, inputs)
    if grid is not None:
        _add_if_fits(candidates, grid, demos)
    resource = _resource_data(instructions, inputs)
    if resource is not None:
        _add_if_fits(candidates, resource, demos)
    if all(isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) for value in inputs):
        rows = [row for table in inputs for row in table]
        fields = _common_fields(rows)
        for field in fields:
            _add(candidates, {"kind": "project", "field": field})
            for descending in (False, True):
                order = {"kind": "order", "field": field, "descending": descending}
                _add(candidates, order)
                for output_field in fields:
                    _add(candidates, {
                        "kind": "compose",
                        "parts": [order, {"kind": "project", "field": output_field}],
                    })
            for op in ("sum", "count", "min", "max"):
                _add(candidates, {"kind": "aggregate", "op": op, "field": field})
        _add(candidates, {"kind": "aggregate", "op": "count"})

        hint_compare = atoms.hints.comparison
        if hint_compare is not None:
            compare_options: list[tuple[str, Any]] = [hint_compare]
        else:
            compare_options = [
                (op, constant)
                for constant in atoms.constants
                if _numeric(constant)
                for op in ("<", "<=", "==", ">=", ">")
            ]
        for filter_field in fields:
            for op, threshold in compare_options:
                filter_node = {"kind": "filter", "field": filter_field, "comparison": op, "value": threshold}
                _add(candidates, {"kind": "compose", "parts": [filter_node, {"kind": "aggregate", "op": "count"}]})
                for value_field in fields:
                    _add(candidates, {
                        "kind": "compose",
                        "parts": [filter_node, {"kind": "aggregate", "op": "sum", "field": value_field}],
                    })

    if all(isinstance(value, Mapping) and ("graph" in value or "edges" in value) for value in inputs):
        _add(candidates, {"kind": "graph_reachable"})
        _add(candidates, {"kind": "shortest_path"})
        outputs = [_demo_parts(item)[1] for item in demos]
        if all(isinstance(item, str) for item in outputs):
            mapping: dict[str, str] = {}
            graph_program = Program.parse({"kind": "graph_reachable"})
            for demo in demos:
                inp, out = _demo_parts(demo)
                key = str(graph_program.run(inp)).lower()
                prior = mapping.get(key)
                if prior is not None and prior != out:
                    mapping = {}
                    break
                mapping[key] = out
            if mapping:
                _add(candidates, {
                    "kind": "label_map",
                    "source": {"kind": "graph_reachable"},
                    "mapping": mapping,
                })

    ordered = tuple(sorted(candidates.values(), key=lambda item: (item.cost, item.digest)))
    return TaskGrammar(
        instructions=instructions,
        demonstrations=demos,
        atoms=atoms,
        programs=ordered,
        source_schema=FiberSchema.infer(first_input),
        target_schema=FiberSchema.infer(first_output),
        config=config,
    )
