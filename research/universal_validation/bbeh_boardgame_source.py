#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import re
from typing import Any, Iterable, Iterator, Mapping

from bbeh_boardgame_ir import Condition, Literal, Rule, Theory
from bbeh_evidence_protocol import canonical_json_bytes

RULE_RE = re.compile(r"^(Rule\d+):\s*(.*?)\s*=>\s*(.*?)\s*$")
PREFERENCE_RE = re.compile(r"^(Rule\d+)\s*>\s*(Rule\d+)\s*$")


def _normalize_term(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Z]", value):
        return "?" + value.lower()
    return value


def parse_literal(text: str) -> Literal:
    value = text.strip()
    negated = value.startswith("~")
    if negated:
        value = value[1:].strip()
    if not (value.startswith("(") and value.endswith(")")):
        raise ValueError(f"invalid literal: {text!r}")
    inner = value[1:-1]
    parts = [part.strip() for part in inner.split(",", 2)]
    if len(parts) not in {2, 3}:
        raise ValueError(f"literal must have two or three terms: {text!r}")
    subject = _normalize_term(parts[0])
    predicate = _normalize_term(parts[1])
    obj = _normalize_term(parts[2]) if len(parts) == 3 else None
    return Literal(subject, predicate, obj, negated)


def parse_rule(line: str) -> Rule:
    match = RULE_RE.fullmatch(line.strip())
    if match is None:
        raise ValueError(f"invalid rule: {line!r}")
    rule_id, antecedent_text, consequent_text = match.groups()
    antecedents: list[Condition] = []
    for raw in antecedent_text.split("^"):
        chunk = raw.strip()
        existential = False
        exists_match = re.match(r"^exists\s+([A-Z])\s+", chunk)
        if exists_match:
            existential = True
            chunk = chunk[exists_match.end() :].strip()
        antecedents.append(Condition(parse_literal(chunk), existential=existential))
    if not antecedents:
        raise ValueError(f"rule has no antecedents: {line!r}")
    return Rule(rule_id, tuple(antecedents), parse_literal(consequent_text))


def parse_theory(text: str, goal: str) -> Theory:
    section: str | None = None
    facts: list[Literal] = []
    rules: list[Rule] = []
    preferences: set[tuple[str, str]] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"Facts:", "Rules:", "Preferences:"}:
            section = line[:-1].lower()
            continue
        if section == "facts":
            facts.append(parse_literal(line))
        elif section == "rules":
            rules.append(parse_rule(line))
        elif section == "preferences":
            match = PREFERENCE_RE.fullmatch(line)
            if match is None:
                raise ValueError(f"invalid preference: {line!r}")
            preferences.add((match.group(1), match.group(2)))
        else:
            raise ValueError(f"content outside a known section: {line!r}")
    return Theory(frozenset(facts), tuple(rules), frozenset(preferences), parse_literal(goal))


def load_source_rows(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"source row {line_number} is not an object")
            yield row


def audit_source_grammar(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    configs = Counter()
    predicate_arities = Counter()
    failures: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        counts["rows"] += 1
        try:
            theory = parse_theory(str(row["theory"]), str(row["goal"]))
        except Exception as exc:
            counts["parse_failures"] += 1
            failures.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
            continue
        counts["facts"] += len(theory.facts)
        counts["rules"] += len(theory.rules)
        counts["preferences"] += len(theory.preferences)
        counts["negated_facts"] += sum(literal.negated for literal in theory.facts)
        counts["negated_consequents"] += sum(rule.consequent.negated for rule in theory.rules)
        counts["existential_conditions"] += sum(
            condition.existential for rule in theory.rules for condition in rule.antecedents
        )
        for literal in list(theory.facts) + [theory.query] + [
            item
            for rule in theory.rules
            for item in (rule.consequent, *(condition.literal for condition in rule.antecedents))
        ]:
            predicate_arities[f"{literal.predicate}/{2 if literal.object is None else 3}"] += 1
        configs[str(row.get("config", ""))] += 1
    return {
        "protocol": "input-only-source-grammar-audit",
        "rows": counts["rows"],
        "parse_failures": counts["parse_failures"],
        "facts": counts["facts"],
        "rules": counts["rules"],
        "preferences": counts["preferences"],
        "negated_facts": counts["negated_facts"],
        "negated_consequents": counts["negated_consequents"],
        "existential_conditions": counts["existential_conditions"],
        "configs": dict(sorted(configs.items())),
        "predicate_arities": dict(sorted(predicate_arities.items())),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_source_grammar(load_source_rows(args.source))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical_json_bytes(report))
    print(json.dumps({key: value for key, value in report.items() if key not in {"failures", "predicate_arities"}}, indent=2))
    if report["parse_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
