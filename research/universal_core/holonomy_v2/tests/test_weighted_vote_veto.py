from dataclasses import dataclass
from typing import Any

import pytest

from universal_core.holonomy_v2.grammar_ext import build_task_grammar_extended
from universal_core.holonomy_v2.loops import LoopKind, build_loops
from universal_core.holonomy_v2.program import BudgetExceeded, Program
from universal_core.holonomy_v2.proposer import JsonProposalBackend, ProposalError
from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import EngineLimits, SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


PROGRAM_DATA = {
    "kind": "weighted_vote_veto",
    "ballots_field": "ballots",
    "choice_field": "option",
    "weight_field": "weight",
    "support_field": "support",
    "veto_field": "veto",
    "threshold": 0,
    "tie_policy": "lexicographic",
    "default": "NONE",
}


def test_weighted_vote_veto_scores_signed_support() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "ballots": [
            {"option": "A", "weight": 3, "support": True, "veto": False},
            {"option": "A", "weight": 1, "support": False, "veto": False},
            {"option": "B", "weight": 4, "support": True, "veto": False},
        ]
    }) == "B"


def test_weighted_vote_veto_excludes_a_vetoed_choice() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "ballots": [
            {"option": "A", "weight": 3, "support": True, "veto": False},
            {"option": "B", "weight": 5, "support": True, "veto": True},
            {"option": "B", "weight": 5, "support": True, "veto": False},
        ]
    }) == "A"


def test_weighted_vote_veto_uses_threshold_default_and_tie_policy() -> None:
    threshold_program = Program.parse({**PROGRAM_DATA, "threshold": 3})
    first_program = Program.parse({**PROGRAM_DATA, "tie_policy": "first"})
    ballots = [
        {"option": "B", "weight": 2, "support": True, "veto": False},
        {"option": "A", "weight": 2, "support": True, "veto": False},
    ]

    assert threshold_program.run({"ballots": ballots}) == "NONE"
    assert Program.parse(PROGRAM_DATA).run({"ballots": ballots}) == "A"
    assert first_program.run({"ballots": ballots}) == "B"


def test_weighted_vote_veto_rejects_invalid_configuration_and_weights() -> None:
    with pytest.raises(ValueError, match="tie policy"):
        Program.parse({**PROGRAM_DATA, "tie_policy": "random"})

    program = Program.parse(PROGRAM_DATA)
    with pytest.raises(ValueError, match="nonnegative"):
        program.run({
            "ballots": [
                {"option": "A", "weight": -1, "support": True, "veto": False},
            ]
        })


def test_weighted_vote_veto_respects_ballot_bound() -> None:
    program = Program.parse(PROGRAM_DATA)
    ballot = {"option": "A", "weight": 1, "support": True, "veto": False}

    with pytest.raises(BudgetExceeded, match="ballot count"):
        program.run({"ballots": [ballot] * 4}, EngineLimits(max_state_count=3))


def test_induces_weighted_vote_veto_from_explicit_policy() -> None:
    demos = (
        Demo({"ballots": [
            {"option": "A", "weight": 3, "support": True, "veto": False},
            {"option": "B", "weight": 2, "support": True, "veto": False},
        ]}, "A"),
        Demo({"ballots": [
            {"option": "A", "weight": 4, "support": True, "veto": True},
            {"option": "B", "weight": 1, "support": True, "veto": False},
        ]}, "B"),
        Demo({"ballots": [
            {"option": "B", "weight": 1, "support": True, "veto": False},
            {"option": "A", "weight": 1, "support": True, "veto": False},
        ]}, "A"),
    )
    instructions = (
        "Use weighted vote with veto. Each ballot has option, weight, support, and veto. "
        "Support adds its weight and opposition subtracts its weight. Any veto eliminates "
        "that option. Return the non-vetoed option with greatest score. Minimum score 0; "
        "break ties lexicographically; otherwise return NONE."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "weighted_vote_veto"
    assert result.program.run({"ballots": [
        {"option": "A", "weight": 5, "support": False, "veto": False},
        {"option": "B", "weight": 2, "support": True, "veto": False},
    ]}) == "B"


def test_weighted_vote_veto_builds_a_ballot_permutation_loop() -> None:
    demos = (Demo({"ballots": [
        {"option": "A", "weight": 2, "support": True, "veto": False},
        {"option": "B", "weight": 1, "support": True, "veto": False},
    ]}, "A"),)
    program = Program.parse(PROGRAM_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    permutations = [item for item in loops.mandatory if item.kind == LoopKind.VOTE_PERMUTATION]
    assert permutations
    assert all(item.expected == "A" for item in permutations)


def test_weighted_vote_veto_proposal_declares_semantic_constants() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "weighted approval with option veto",
        "confidence": 0.9,
        "declared_constants": [0, "NONE"],
    })

    proposals = backend.propose(
        "Use weighted vote with veto.",
        (Demo({"ballots": [
            {"option": "A", "weight": 1, "support": True, "veto": False},
        ]}, "A"),),
        (0, "NONE"),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "weighted_vote_veto"


def test_weighted_vote_veto_proposal_rejects_undeclared_default() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "hidden fallback",
        "confidence": 0.9,
        "declared_constants": [0],
    })

    with pytest.raises(ProposalError, match="undeclared constant"):
        backend.propose(
            "Use weighted vote with veto.",
            (Demo({"ballots": [
                {"option": "A", "weight": 1, "support": True, "veto": False},
            ]}, "A"),),
            (0, "NONE"),
        )
