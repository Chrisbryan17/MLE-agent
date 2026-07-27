#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable, Mapping

from bbeh_boardgame_ir import Condition, Derivation, Literal, ProofResult, Rule, Theory, is_variable

Substitution = dict[str, str | None]
BackgroundEvaluator = Callable[[Literal, frozenset[Literal]], bool]


def _unify_term(pattern: str | None, value: str | None, subst: Substitution) -> Substitution | None:
    if is_variable(pattern):
        assert isinstance(pattern, str)
        if pattern in subst:
            return subst if subst[pattern] == value else None
        out = dict(subst)
        out[pattern] = value
        return out
    return subst if pattern == value else None


def _unify(pattern: Literal, value: Literal, subst: Substitution) -> Substitution | None:
    if pattern.predicate != value.predicate or pattern.negated != value.negated:
        return None
    current = _unify_term(pattern.subject, value.subject, subst)
    if current is None:
        return None
    return _unify_term(pattern.object, value.object, current)


def _instantiate_term(term: str | None, subst: Mapping[str, str | None]) -> str | None:
    if is_variable(term):
        assert isinstance(term, str)
        return subst.get(term, term)
    return term


def _instantiate(literal: Literal, subst: Mapping[str, str | None]) -> Literal:
    subject = _instantiate_term(literal.subject, subst)
    if not isinstance(subject, str) or is_variable(subject):
        raise ValueError(f"unbound subject variable in {literal}")
    obj = _instantiate_term(literal.object, subst)
    if is_variable(obj):
        raise ValueError(f"unbound object variable in {literal}")
    return Literal(subject, literal.predicate, obj, literal.negated)


def _dedupe_substitutions(items: Iterable[Substitution]) -> list[Substitution]:
    seen: set[tuple[tuple[str, str | None], ...]] = set()
    out: list[Substitution] = []
    for item in items:
        signature = tuple(sorted(item.items()))
        if signature not in seen:
            seen.add(signature)
            out.append(item)
    return out


def _condition_matches(
    condition: Condition,
    active: frozenset[Literal],
    substitutions: list[Substitution],
    facts: frozenset[Literal],
    background: BackgroundEvaluator | None,
) -> list[tuple[Substitution, Literal]]:
    matches: list[tuple[Substitution, Literal]] = []
    for subst in substitutions:
        for candidate in active:
            unified = _unify(condition.literal, candidate, subst)
            if unified is not None:
                matches.append((unified, candidate))
        try:
            grounded = _instantiate(condition.literal, subst)
        except ValueError:
            grounded = None
        if grounded is not None and background is not None and background(grounded, facts):
            matches.append((dict(subst), grounded))
    return matches


def _applicable_derivations(
    rule: Rule,
    active: frozenset[Literal],
    facts: frozenset[Literal],
    background: BackgroundEvaluator | None,
) -> list[Derivation]:
    states: list[tuple[Substitution, tuple[Literal, ...]]] = [({}, ())]
    for condition in rule.antecedents:
        next_states: list[tuple[Substitution, tuple[Literal, ...]]] = []
        for subst, premises in states:
            matches = _condition_matches(condition, active, [subst], facts, background)
            for new_subst, supporting_literal in matches:
                next_states.append((new_subst, premises + (supporting_literal,)))
        if not next_states:
            return []
        deduped = _dedupe_substitutions([subst for subst, _ in next_states])
        allowed = {tuple(sorted(item.items())) for item in deduped}
        states = [state for state in next_states if tuple(sorted(state[0].items())) in allowed]

    out: list[Derivation] = []
    seen: set[tuple[Literal, tuple[Literal, ...]]] = set()
    for subst, premises in states:
        try:
            consequent = _instantiate(rule.consequent, subst)
        except ValueError:
            continue
        signature = (consequent, premises)
        if signature not in seen:
            seen.add(signature)
            out.append(Derivation(consequent, rule.rule_id, premises))
    return out


def _preference_closure(preferences: frozenset[tuple[str, str]]) -> frozenset[tuple[str, str]]:
    closure = set(preferences)
    changed = True
    while changed:
        changed = False
        additions: set[tuple[str, str]] = set()
        for stronger, middle in closure:
            for middle2, weaker in closure:
                if middle == middle2 and stronger != weaker and (stronger, weaker) not in closure:
                    additions.add((stronger, weaker))
        if additions:
            closure.update(additions)
            changed = True
    return frozenset(closure)


def _strictly_stronger(left: Derivation, right: Derivation, closure: frozenset[tuple[str, str]]) -> bool:
    if left.rule_id is None or right.rule_id is None:
        return False
    return (left.rule_id, right.rule_id) in closure


def _resolve_candidates(
    candidates: Mapping[Literal, list[Derivation]],
    closure: frozenset[tuple[str, str]],
) -> dict[Literal, tuple[Derivation, ...]]:
    resolved: dict[Literal, tuple[Derivation, ...]] = {}
    visited: set[Literal] = set()
    for literal in sorted(candidates):
        if literal in visited:
            continue
        opposite = literal.opposite()
        visited.add(literal)
        visited.add(opposite)
        left = list(candidates.get(literal, ()))
        right = list(candidates.get(opposite, ()))
        if not right:
            if left:
                resolved[literal] = tuple(left)
            continue
        if not left:
            resolved[opposite] = tuple(right)
            continue

        surviving_left = [
            derivation
            for derivation in left
            if not any(_strictly_stronger(opponent, derivation, closure) for opponent in right)
        ]
        surviving_right = [
            derivation
            for derivation in right
            if not any(_strictly_stronger(opponent, derivation, closure) for opponent in left)
        ]
        if surviving_left and not surviving_right:
            resolved[literal] = tuple(surviving_left)
        elif surviving_right and not surviving_left:
            resolved[opposite] = tuple(surviving_right)
    return resolved


def prove(
    theory: Theory,
    background: BackgroundEvaluator | None = None,
    max_iterations: int | None = None,
) -> ProofResult:
    closure = _preference_closure(theory.preferences)
    fact_derivations = {literal: [Derivation(literal, None, ())] for literal in theory.facts}
    active_map: dict[Literal, tuple[Derivation, ...]] = {
        literal: tuple(items) for literal, items in fact_derivations.items()
    }
    limit = max_iterations or max(4, len(theory.rules) * 3 + 4)

    for _ in range(limit):
        active = frozenset(active_map)
        candidates: dict[Literal, list[Derivation]] = defaultdict(list)
        for literal, derivations in fact_derivations.items():
            candidates[literal].extend(derivations)
        for rule in theory.rules:
            for derivation in _applicable_derivations(rule, active, theory.facts, background):
                if derivation not in candidates[derivation.literal]:
                    candidates[derivation.literal].append(derivation)
        next_map = _resolve_candidates(candidates, closure)
        if next_map == active_map:
            break
        active_map = next_map
    else:
        raise RuntimeError("defeasible inference did not converge")

    query_derivations = active_map.get(theory.query, ())
    opposite_derivations = active_map.get(theory.query.opposite(), ())
    if query_derivations and not opposite_derivations:
        status = "proved"
    elif opposite_derivations and not query_derivations:
        status = "disproved"
    else:
        status = "unknown"
    return ProofResult(
        status=status,
        query_derivations=tuple(query_derivations),
        opposite_derivations=tuple(opposite_derivations),
        active_literals=frozenset(active_map),
    )
