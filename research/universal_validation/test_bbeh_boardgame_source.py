from __future__ import annotations

import gzip
import json
from pathlib import Path

from bbeh_boardgame_ir import Literal
from bbeh_boardgame_source import audit_source_grammar, load_source_rows, parse_theory


SOURCE = """Facts:
\t(coyote, swear, pigeon)
\t~(shark, capture, gorilla)
Rules:
\tRule2: ~(X, shout, peafowl)^(X, take, gadwall) => (X, bring, woodpecker)
\tRule5: exists X (X, destroy, frog) => ~(shark, bring, cougar)
Preferences:
\tRule1 > Rule8
"""


def test_parse_structured_theory() -> None:
    theory = parse_theory(SOURCE, "(pigeon, bring, woodpecker)")
    assert Literal("coyote", "swear", "pigeon") in theory.facts
    assert Literal("shark", "capture", "gorilla", True) in theory.facts
    assert theory.rules[0].antecedents[0].literal == Literal("?x", "shout", "peafowl", True)
    assert theory.rules[0].antecedents[1].literal == Literal("?x", "take", "gadwall")
    assert theory.rules[1].antecedents[0].existential
    assert theory.rules[1].consequent == Literal("shark", "bring", "cougar", True)
    assert ("Rule1", "Rule8") in theory.preferences
    assert theory.query == Literal("pigeon", "bring", "woodpecker")


def test_jsonl_loader_preserves_rows(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl.gz"
    rows = [{"theory": SOURCE, "goal": "(pigeon, bring, woodpecker)", "config": "x"}]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    assert list(load_source_rows(path)) == rows


def test_audit_never_reads_label_or_proof(tmp_path: Path) -> None:
    class Guarded(dict):
        def __getitem__(self, key: str):
            if key in {"label", "proof"}:
                raise AssertionError(f"forbidden access: {key}")
            return super().__getitem__(key)

    report = audit_source_grammar(
        [Guarded(theory=SOURCE, goal="(pigeon, bring, woodpecker)", config="ManyDistractors-depth2")]
    )
    assert report["rows"] == 1
    assert report["parse_failures"] == 0
    assert report["facts"] == 2
    assert report["rules"] == 2
    assert report["preferences"] == 1
    assert report["existential_conditions"] == 1
