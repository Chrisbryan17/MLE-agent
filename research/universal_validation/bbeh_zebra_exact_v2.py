#!/usr/bin/env python3
from __future__ import annotations

import itertools

import bbeh_zebra_exact_v1 as base

Problem = base.Problem
Relation = base.Relation
parse_problem = base.parse_problem
compile_clue = base.compile_clue
z3 = base.z3
_all_values = base._all_values
_query_value = base._query_value
_fixed_position = base._fixed_position
_relation_holds = base._relation_holds
_solve_small = base._solve_small


def _copy_domains(domains: dict[str, set[int]]) -> dict[str, set[int]]:
    return {value: set(options) for value, options in domains.items()}


def _relation_variables(relation: Relation) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value for value in relation.values if _fixed_position(value) is None
        )
    )


def _relation_supports(
    relation: Relation,
    domains: dict[str, set[int]],
    size: int,
    fixed_variable: str,
    fixed_value: int,
) -> bool:
    remaining = [
        value for value in _relation_variables(relation) if value != fixed_variable
    ]
    option_sets = [sorted(domains[value]) for value in remaining]
    for choices in itertools.product(*option_sets):
        assignment = {fixed_variable: fixed_value}
        assignment.update(zip(remaining, choices))
        if _relation_holds(relation, assignment, size):
            return True
    return False


def _propagate_relations(
    domains: dict[str, set[int]],
    relations: list[Relation],
    size: int,
) -> tuple[bool, bool]:
    changed = False
    for relation in relations:
        for variable in _relation_variables(relation):
            supported = {
                value
                for value in domains[variable]
                if _relation_supports(relation, domains, size, variable, value)
            }
            if not supported:
                return changed, False
            if supported != domains[variable]:
                domains[variable] = supported
                changed = True
    return changed, True


def _propagate_all_different(
    domains: dict[str, set[int]],
    categories: list[tuple[str, ...]],
    size: int,
) -> tuple[bool, bool]:
    changed = False
    positions = set(range(1, size + 1))
    for category in categories:
        singleton_values = [
            next(iter(domains[value]))
            for value in category
            if len(domains[value]) == 1
        ]
        if len(singleton_values) != len(set(singleton_values)):
            return changed, False
        reserved = set(singleton_values)
        for value in category:
            if len(domains[value]) > 1:
                reduced = domains[value] - reserved
                if not reduced:
                    return changed, False
                if reduced != domains[value]:
                    domains[value] = reduced
                    changed = True

        for position in positions:
            holders = [value for value in category if position in domains[value]]
            if not holders:
                return changed, False
            if len(holders) == 1 and domains[holders[0]] != {position}:
                domains[holders[0]] = {position}
                changed = True

        category_values = list(category)
        for subset_size in range(2, len(category_values)):
            for subset in itertools.combinations(category_values, subset_size):
                union = set().union(*(domains[value] for value in subset))
                if len(union) < subset_size:
                    return changed, False
                if len(union) != subset_size:
                    continue
                subset_set = set(subset)
                for other in category_values:
                    if other in subset_set:
                        continue
                    reduced = domains[other] - union
                    if not reduced:
                        return changed, False
                    if reduced != domains[other]:
                        domains[other] = reduced
                        changed = True
    return changed, True


def _propagate_csp(
    domains: dict[str, set[int]],
    problem: Problem,
    relations: list[Relation],
) -> dict[str, set[int]] | None:
    categories = list(problem.categories.values())
    while True:
        changed = False
        all_diff_changed, valid = _propagate_all_different(
            domains, categories, problem.size
        )
        if not valid:
            return None
        changed |= all_diff_changed
        relation_changed, valid = _propagate_relations(
            domains, relations, problem.size
        )
        if not valid:
            return None
        changed |= relation_changed
        if not changed:
            return domains


def _csp_satisfiable(
    domains: dict[str, set[int]],
    problem: Problem,
    relations: list[Relation],
    degrees: dict[str, int],
) -> bool:
    propagated = _propagate_csp(_copy_domains(domains), problem, relations)
    if propagated is None:
        return False
    unresolved = [value for value, options in propagated.items() if len(options) > 1]
    if not unresolved:
        assignment = {
            value: next(iter(options)) for value, options in propagated.items()
        }
        return all(
            _relation_holds(relation, assignment, problem.size)
            for relation in relations
        )
    variable = min(
        unresolved,
        key=lambda value: (len(propagated[value]), -degrees.get(value, 0), value),
    )
    for position in sorted(propagated[variable]):
        child = _copy_domains(propagated)
        child[variable] = {position}
        if _csp_satisfiable(child, problem, relations, degrees):
            return True
    return False


def _solve_csp(problem: Problem, relations: list[Relation]) -> str | None:
    all_values = _all_values(problem)
    if len(set(all_values)) != len(all_values):
        raise ValueError("duplicate entity surface forms are ambiguous")
    domains = {
        value: set(range(1, problem.size + 1))
        for value in all_values
    }
    propagated = _propagate_csp(domains, problem, relations)
    if propagated is None:
        return None
    target = _query_value(problem)
    degrees = {value: 0 for value in all_values}
    for relation in relations:
        for value in _relation_variables(relation):
            degrees[value] += 1
    possible: list[int] = []
    for position in sorted(propagated[target]):
        candidate_domains = _copy_domains(propagated)
        candidate_domains[target] = {position}
        if _csp_satisfiable(candidate_domains, problem, relations, degrees):
            possible.append(position)
            if len(possible) > 1:
                return None
    return str(possible[0]) if len(possible) == 1 else None


def solve(text: str) -> str | None:
    problem = parse_problem(text)
    all_values = _all_values(problem)
    relations = [compile_clue(clue, all_values) for clue in problem.clues]
    if z3 is not None:
        return base._solve_z3(problem, relations)
    return _solve_csp(problem, relations)
