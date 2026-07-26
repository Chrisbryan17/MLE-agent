from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


@dataclass(frozen=True)
class Constraint:
    scope: tuple[str, ...]
    allowed: frozenset[tuple[bool, ...]]


def entity(raw: str, aliases: dict[str, str]) -> str:
    raw = raw.strip().rstrip('.,?')
    match = re.fullmatch(r'the person at the (.+)', raw, re.I)
    if match:
        return '@' + match.group(1).strip().lower()
    return aliases.get(raw, raw)


def relation(scope_names, predicate) -> Constraint:
    scope = tuple(dict.fromkeys(scope_names))
    allowed = set()
    for bits in itertools.product((False, True), repeat=len(scope)):
        assignment = dict(zip(scope, bits))
        if predicate(assignment):
            allowed.add(bits)
    return Constraint(scope, frozenset(allowed))


def statement_constraint(speaker: str, names: list[str], content_predicate) -> Constraint:
    return relation([speaker] + names, lambda a: a[speaker] == bool(content_predicate(a)))


def parse_content(speaker: str, content: str, aliases: dict[str, str]) -> Constraint:
    content = content.strip().rstrip('.')
    low = content.lower()
    trio = re.search(r'([A-Z][A-Za-z]+),\s*([A-Z][A-Za-z]+)\s+and\s+([A-Z][A-Za-z]+)', content)
    if trio:
        names = [entity(name, aliases) for name in trio.groups()]
        if low.startswith('only one of') and low.endswith('lies'):
            counts = {2}
        elif low.startswith('only one of') and 'tell' in low and 'truth' in low:
            counts = {1}
        elif low.startswith('exactly one of') and 'tell' in low and 'truth' in low:
            counts = {1}
        elif low.startswith('exactly two of') and 'tell' in low and 'truth' in low:
            counts = {2}
        elif re.match(r'^[A-Z][A-Za-z]+,', content) and 'all tell the truth' in low:
            counts = {3}
        elif low.startswith('either exactly two of') and 'or none of them' in low:
            counts = {0, 2}
        elif low.startswith('either exactly one of') and 'or all three of them' in low:
            counts = {1, 3}
        elif low.startswith('either all three of') and 'lie' in low and 'two of them tell the truth' in low:
            counts = {0, 2}
        elif low.startswith('either all three of') and 'tell the truth or only one of them' in low:
            counts = {1, 3}
        else:
            raise ValueError(f'Unparsed cardinal statement: {content!r}')
        return statement_constraint(
            speaker,
            names,
            lambda a: sum(bool(a[name]) for name in names) in counts,
        )

    binary = re.fullmatch(r'(.+?) tells the truth', content, re.I)
    if binary:
        target = entity(binary.group(1), aliases)
        return statement_constraint(speaker, [target], lambda a: a[target])
    binary = re.fullmatch(r'(.+?) lies', content, re.I)
    if binary:
        target = entity(binary.group(1), aliases)
        return statement_constraint(speaker, [target], lambda a: not a[target])
    raise ValueError(f'Unparsed statement content: {content!r}')


def parse(text: str) -> tuple[list[Constraint], list[str]]:
    query_match = re.search(r'(Does the person at the|Do\s+[A-Z])', text)
    if not query_match:
        raise ValueError('Query not found')
    declarative = text[:query_match.start()]
    query_text = text[query_match.start():]
    declarative = re.sub(r'\.(?=[A-Z])', '. ', declarative)

    aliases: dict[str, str] = {}
    for name, location in re.findall(r'\b([A-Z][A-Za-z]+) is at the ([a-z ]+?)\.', declarative):
        aliases[name] = '@' + location.strip().lower()

    constraints: list[Constraint] = []
    for sentence in re.split(r'(?<=\.)\s+', declarative):
        sentence = sentence.strip()
        if not sentence or sentence.startswith('In this question'):
            continue
        if re.fullmatch(r'[A-Z][A-Za-z]+ is at the [a-z ]+\.', sentence):
            continue
        if re.fullmatch(r'The person at the [a-z ]+ (?:thinks .+|saw a firetruck)\.', sentence, re.I):
            continue
        direct = re.fullmatch(r'(.+?) tells the truth\.', sentence, re.I)
        if direct and ' says ' not in sentence.lower():
            subject = entity(direct.group(1), aliases)
            constraints.append(Constraint((subject,), frozenset({(True,)})))
            continue
        direct = re.fullmatch(r'(.+?) lies\.', sentence, re.I)
        if direct and ' says ' not in sentence.lower():
            subject = entity(direct.group(1), aliases)
            constraints.append(Constraint((subject,), frozenset({(False,)})))
            continue
        said = re.fullmatch(r'(.+?) says (.+)\.', sentence, re.I)
        if said:
            speaker = entity(said.group(1), aliases)
            constraints.append(parse_content(speaker, said.group(2), aliases))
            continue
        raise ValueError(f'Unparsed sentence: {sentence!r}')

    location_queries = re.findall(r'Does the person at the ([a-z ]+?) tell the truth\?', query_text, re.I)
    if location_queries:
        queries = ['@' + location.strip().lower() for location in location_queries]
    else:
        named = re.search(r'Do\s+(.+?)\s+tell the truth\?', query_text, re.I | re.S)
        if not named:
            raise ValueError('Named query not parsed')
        queries = [entity(name, aliases) for name in re.findall(r'[A-Z][A-Za-z]+', named.group(1))]
    if len(queries) != 3:
        raise ValueError(f'Expected three queries, got {queries}')
    return constraints, queries


def component(query: str, constraints: list[Constraint]) -> tuple[set[str], list[Constraint]]:
    names = {query}
    changed = True
    while changed:
        changed = False
        for constraint in constraints:
            if names.intersection(constraint.scope) and not set(constraint.scope).issubset(names):
                names.update(constraint.scope)
                changed = True
    return names, [c for c in constraints if set(c.scope).issubset(names)]


def satisfiable(constraints: list[Constraint], fixed: dict[str, bool]) -> bool:
    names = sorted(set(fixed) | {name for c in constraints for name in c.scope})
    variable = {name: index for index, name in enumerate(names)}
    next_variable = len(names)
    compiled = []
    for constraint in constraints:
        allowed = list(constraint.allowed)
        indicators = list(range(next_variable, next_variable + len(allowed)))
        next_variable += len(allowed)
        compiled.append((constraint, allowed, indicators))

    rows: list[dict[int, float]] = []
    right_hand_side: list[float] = []
    for name, value in fixed.items():
        rows.append({variable[name]: 1.0})
        right_hand_side.append(float(value))
    for constraint, allowed, indicators in compiled:
        rows.append({indicator: 1.0 for indicator in indicators})
        right_hand_side.append(1.0)
        for position, name in enumerate(constraint.scope):
            row = {variable[name]: 1.0}
            for values, indicator in zip(allowed, indicators):
                if values[position]:
                    row[indicator] = row.get(indicator, 0.0) - 1.0
            rows.append(row)
            right_hand_side.append(0.0)

    matrix = lil_matrix((len(rows), next_variable), dtype=float)
    for row_index, entries in enumerate(rows):
        for column, coefficient in entries.items():
            matrix[row_index, column] = coefficient
    rhs = np.asarray(right_hand_side, dtype=float)
    result = milp(
        c=np.zeros(next_variable, dtype=float),
        integrality=np.ones(next_variable, dtype=int),
        bounds=Bounds(np.zeros(next_variable), np.ones(next_variable)),
        constraints=LinearConstraint(matrix.tocsr(), rhs, rhs),
        options={'presolve': True},
    )
    return bool(result.success)


def solve(text: str) -> str | None:
    constraints, queries = parse(text)
    answers = []
    for query in queries:
        _, relevant = component(query, constraints)
        can_true = satisfiable(relevant, {query: True})
        can_false = satisfiable(relevant, {query: False})
        if can_true and not can_false:
            answers.append('yes')
        elif can_false and not can_true:
            answers.append('no')
        else:
            answers.append('unknown')
    return ', '.join(answers)
