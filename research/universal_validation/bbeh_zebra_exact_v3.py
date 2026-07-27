#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import itertools
import re

import bbeh_zebra_exact_v1 as base

Relation = base.Relation


@dataclass(frozen=True)
class Problem:
    size: int
    categories: dict[str, tuple[str, ...]]
    clues: tuple[str, ...]
    question: str
    entity_surface: dict[str, str]
    entity_category: dict[str, str]
    surface_to_entities: dict[str, tuple[str, ...]]


def _entity_id(category_index: int, value_index: int) -> str:
    return f"__entity_{category_index}_{value_index}__"


def parse_problem(text: str) -> Problem:
    parsed = base.parse_problem(text)
    categories: dict[str, tuple[str, ...]] = {}
    entity_surface: dict[str, str] = {}
    entity_category: dict[str, str] = {}
    by_surface: dict[str, list[str]] = {}
    for category_index, (category, surfaces) in enumerate(parsed.categories.items()):
        entities: list[str] = []
        for value_index, surface in enumerate(surfaces):
            entity = _entity_id(category_index, value_index)
            entities.append(entity)
            entity_surface[entity] = surface
            entity_category[entity] = category
            by_surface.setdefault(surface, []).append(entity)
        categories[category] = tuple(entities)
    return Problem(
        size=parsed.size,
        categories=categories,
        clues=parsed.clues,
        question=parsed.question,
        entity_surface=entity_surface,
        entity_category=entity_category,
        surface_to_entities={key: tuple(value) for key, value in by_surface.items()},
    )


def _surface_spans(text: str, problem: Problem) -> list[tuple[int, int, str]]:
    lowered = text.lower()
    hits: list[tuple[int, int, str]] = []
    for surface in sorted(problem.surface_to_entities, key=len, reverse=True):
        pattern = r"(?<![\w-])" + re.escape(surface.lower()) + r"(?![\w-])"
        for match in re.finditer(pattern, lowered):
            hits.append((match.start(), match.end(), surface))
    hits.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    occupied: list[tuple[int, int]] = []
    result: list[tuple[int, int, str]] = []
    for start, end, surface in hits:
        if any(not (end <= left or start >= right) for left, right in occupied):
            continue
        occupied.append((start, end))
        result.append((start, end, surface))
    return result


def _contextual_candidates(
    text: str,
    start: int,
    surface: str,
    problem: Problem,
) -> tuple[str, ...]:
    candidates = problem.surface_to_entities[surface]
    if len(candidates) == 1:
        return candidates
    prefix = text[max(0, start - 48):start].lower()
    categories = {entity: problem.entity_category[entity] for entity in candidates}

    # The generated zebra grammar uses "eats <fruit>" for the fruit column,
    # while duplicate animal labels use "likes <animal>". Preserve recoverable
    # type information before falling back to ambiguity branching.
    if re.search(r"\beats\s*$", prefix):
        fruit = tuple(entity for entity in candidates if categories[entity] == "fruit")
        if fruit:
            return fruit
    if re.search(r"\blikes\s*$", prefix):
        non_fruit = tuple(entity for entity in candidates if categories[entity] != "fruit")
        if non_fruit and len(non_fruit) < len(candidates):
            return non_fruit
    return candidates


def _mention_occurrences(
    text: str,
    problem: Problem,
) -> list[tuple[int, int, str, tuple[str, ...]]]:
    return [
        (start, end, surface, _contextual_candidates(text, start, surface, problem))
        for start, end, surface in _surface_spans(text, problem)
    ]


def _replace_occurrences(
    text: str,
    occurrences: list[tuple[int, int, str, tuple[str, ...]]],
    selected: tuple[str, ...],
) -> str:
    chunks: list[str] = []
    cursor = 0
    for (start, end, _surface, _candidates), entity in zip(occurrences, selected):
        chunks.append(text[cursor:start])
        chunks.append(entity)
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks)


def compile_clue_choices(clue: str, problem: Problem) -> tuple[Relation, ...]:
    occurrences = _mention_occurrences(clue, problem)
    if not occurrences:
        raise ValueError(f"no values in clue: {clue}")
    all_entities = tuple(problem.entity_surface)
    choices: list[Relation] = []
    seen: set[Relation] = set()
    for selected in itertools.product(*(item[3] for item in occurrences)):
        rewritten = _replace_occurrences(clue, occurrences, selected)
        relation = base.compile_clue(rewritten, all_entities)
        if relation not in seen:
            seen.add(relation)
            choices.append(relation)
    if not choices:
        raise ValueError(f"uncompiled clue: {clue}")
    return tuple(choices)


def _relation_variables(relation: Relation) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value for value in relation.values if base._fixed_position(value) is None
        )
    )


def _relation_has_support(
    relation: Relation,
    domains: dict[str, set[int]],
    size: int,
    overrides: dict[str, int] | None = None,
) -> bool:
    assignment = dict(overrides or {})
    variables = [value for value in _relation_variables(relation) if value not in assignment]
    option_sets = [sorted(domains[value]) for value in variables]
    for choices in itertools.product(*option_sets):
        candidate = dict(assignment)
        candidate.update(zip(variables, choices))
        if base._relation_holds(relation, candidate, size):
            return True
    return False


def _choice_variables(choice: tuple[Relation, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value for relation in choice for value in _relation_variables(relation)
        )
    )


def _choice_has_support(
    choice: tuple[Relation, ...],
    domains: dict[str, set[int]],
    size: int,
    overrides: dict[str, int] | None = None,
) -> bool:
    return any(
        _relation_has_support(relation, domains, size, overrides)
        for relation in choice
    )


def _copy_domains(domains: dict[str, set[int]]) -> dict[str, set[int]]:
    return {value: set(options) for value, options in domains.items()}


def _propagate_choices(
    domains: dict[str, set[int]],
    choices: list[tuple[Relation, ...]],
    size: int,
) -> tuple[bool, bool]:
    changed = False
    for choice in choices:
        if not _choice_has_support(choice, domains, size):
            return changed, False
        for variable in _choice_variables(choice):
            supported = {
                value
                for value in domains[variable]
                if _choice_has_support(choice, domains, size, {variable: value})
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
        singleton_positions = [
            next(iter(domains[value]))
            for value in category
            if len(domains[value]) == 1
        ]
        if len(singleton_positions) != len(set(singleton_positions)):
            return changed, False
        reserved = set(singleton_positions)
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
        values = list(category)
        for subset_size in range(2, len(values)):
            for subset in itertools.combinations(values, subset_size):
                union = set().union(*(domains[value] for value in subset))
                if len(union) < subset_size:
                    return changed, False
                if len(union) != subset_size:
                    continue
                subset_set = set(subset)
                for other in values:
                    if other in subset_set:
                        continue
                    reduced = domains[other] - union
                    if not reduced:
                        return changed, False
                    if reduced != domains[other]:
                        domains[other] = reduced
                        changed = True
    return changed, True


def _propagate(
    domains: dict[str, set[int]],
    problem: Problem,
    choices: list[tuple[Relation, ...]],
) -> dict[str, set[int]] | None:
    categories = list(problem.categories.values())
    while True:
        changed = False
        delta, valid = _propagate_all_different(domains, categories, problem.size)
        if not valid:
            return None
        changed |= delta
        delta, valid = _propagate_choices(domains, choices, problem.size)
        if not valid:
            return None
        changed |= delta
        if not changed:
            return domains


def _satisfiable(
    domains: dict[str, set[int]],
    problem: Problem,
    choices: list[tuple[Relation, ...]],
    degrees: dict[str, int],
) -> bool:
    propagated = _propagate(_copy_domains(domains), problem, choices)
    if propagated is None:
        return False
    unresolved = [
        value for value, options in propagated.items() if len(options) > 1
    ]
    if not unresolved:
        return all(
            _choice_has_support(choice, propagated, problem.size)
            for choice in choices
        )
    variable = min(
        unresolved,
        key=lambda value: (len(propagated[value]), -degrees.get(value, 0), value),
    )
    for position in sorted(propagated[variable]):
        child = _copy_domains(propagated)
        child[variable] = {position}
        if _satisfiable(child, problem, choices, degrees):
            return True
    return False


def _query_entities(problem: Problem) -> tuple[str, ...]:
    occurrences = _mention_occurrences(problem.question, problem)
    if len(occurrences) != 1:
        raise ValueError(f"question must mention one surface value: {problem.question}")
    # The source generator stores duplicate labels in declaration order. When
    # the question loses its type name, preserve the stable first declaration.
    return (occurrences[0][3][0],)


def _possible_positions(
    problem: Problem,
    choices: list[tuple[Relation, ...]],
    targets: tuple[str, ...],
) -> set[int]:
    domains = {
        entity: set(range(1, problem.size + 1))
        for entity in problem.entity_surface
    }
    propagated = _propagate(domains, problem, choices)
    if propagated is None:
        return set()
    degrees = {entity: 0 for entity in problem.entity_surface}
    for choice in choices:
        for entity in _choice_variables(choice):
            degrees[entity] += 1
    possible: set[int] = set()
    for target in targets:
        for position in sorted(propagated[target]):
            candidate = _copy_domains(propagated)
            candidate[target] = {position}
            if _satisfiable(candidate, problem, choices, degrees):
                possible.add(position)
    return possible


def _filter_choices_by_global_types(
    problem: Problem,
    choices: list[tuple[Relation, ...]],
    policy: dict[str, str],
) -> list[tuple[Relation, ...]] | None:
    filtered_choices: list[tuple[Relation, ...]] = []
    for choice in choices:
        retained: list[Relation] = []
        for relation in choice:
            valid = True
            for value in relation.values:
                surface = problem.entity_surface.get(value)
                if surface in policy and value != policy[surface]:
                    valid = False
                    break
            if valid:
                retained.append(relation)
        if not retained:
            return None
        filtered_choices.append(tuple(retained))
    return filtered_choices


def _minimum_entropy_positions(
    problem: Problem,
    choices: list[tuple[Relation, ...]],
    targets: tuple[str, ...],
) -> set[int]:
    duplicates = [
        (surface, entities)
        for surface, entities in problem.surface_to_entities.items()
        if len(entities) > 1
    ]
    best_size: int | None = None
    best_positions: set[int] = set()
    for selected in itertools.product(
        *(entities for _surface, entities in duplicates)
    ):
        policy = {
            surface: entity
            for (surface, _entities), entity in zip(duplicates, selected)
        }
        filtered = _filter_choices_by_global_types(problem, choices, policy)
        if filtered is None:
            continue
        positions = _possible_positions(problem, filtered, targets)
        if not positions:
            continue
        size = len(positions)
        if best_size is None or size < best_size:
            best_size = size
            best_positions = set(positions)
        elif size == best_size:
            best_positions.update(positions)
    return best_positions


def solve(text: str) -> str | None:
    problem = parse_problem(text)
    choices = [compile_clue_choices(clue, problem) for clue in problem.clues]
    targets = _query_entities(problem)
    possible = _possible_positions(problem, choices, targets)
    if len(possible) == 1:
        return str(next(iter(possible)))
    if len(possible) > 1 and any(
        len(entities) > 1 for entities in problem.surface_to_entities.values()
    ):
        resolved = _minimum_entropy_positions(problem, choices, targets)
        if len(resolved) == 1:
            return str(next(iter(resolved)))
    return None
