#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

Term: TypeAlias = str | None


def is_variable(term: Term) -> bool:
    return isinstance(term, str) and term.startswith("?")


@dataclass(frozen=True, order=True)
class Literal:
    subject: str
    predicate: str
    object: Term = None
    negated: bool = False

    def opposite(self) -> "Literal":
        return Literal(self.subject, self.predicate, self.object, not self.negated)


@dataclass(frozen=True)
class Condition:
    literal: Literal
    existential: bool = False


@dataclass(frozen=True)
class Rule:
    rule_id: str
    antecedents: tuple[Condition, ...]
    consequent: Literal


@dataclass(frozen=True)
class Theory:
    facts: frozenset[Literal]
    rules: tuple[Rule, ...]
    preferences: frozenset[tuple[str, str]]
    query: Literal


@dataclass(frozen=True)
class Derivation:
    literal: Literal
    rule_id: str | None
    premises: tuple[Literal, ...] = ()


@dataclass(frozen=True)
class ProofResult:
    status: str
    query_derivations: tuple[Derivation, ...]
    opposite_derivations: tuple[Derivation, ...]
    active_literals: frozenset[Literal]
