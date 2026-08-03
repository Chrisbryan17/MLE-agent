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
    "kind": "distinct_slot_match",
    "items_field": "items",
    "id_field": "id",
    "slots_field": "slots",
    "success": "YES",
    "failure": "NO",
}


def test_distinct_slot_match_accepts_a_complete_matching() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "items": [
            {"id": "A", "slots": [1, 2]},
            {"id": "B", "slots": [2, 3]},
            {"id": "C", "slots": [1, 3]},
        ],
    }) == "YES"


def test_distinct_slot_match_rejects_a_hall_deficit() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "items": [
            {"id": "A", "slots": [1]},
            {"id": "B", "slots": [1]},
        ],
    }) == "NO"


def test_distinct_slot_match_uses_augmenting_paths_not_greedy_choice() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "items": [
            {"id": "A", "slots": [1, 2]},
            {"id": "B", "slots": [1]},
        ],
    }) == "YES"


def test_distinct_slot_match_handles_structured_slot_values() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "items": [
            {"id": "A", "slots": [{"day": 1}, {"day": 2}]},
            {"id": "B", "slots": [{"day": 1}]},
        ],
    }) == "YES"


def test_distinct_slot_match_rejects_duplicate_item_ids_and_bad_slots() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(ValueError, match="duplicate item id"):
        program.run({
            "items": [
                {"id": "A", "slots": [1]},
                {"id": "A", "slots": [2]},
            ],
        })

    with pytest.raises(TypeError, match="slots must be a sequence"):
        program.run({"items": [{"id": "A", "slots": 1}]})


def test_distinct_slot_match_respects_item_bound() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(BudgetExceeded, match="item count"):
        program.run(
            {
                "items": [
                    {"id": "A", "slots": [1]},
                    {"id": "B", "slots": [2]},
                ],
            },
            EngineLimits(max_state_count=1),
        )


def test_induces_distinct_slot_match_from_explicit_policy() -> None:
    demos = (
        Demo({
            "items": [
                {"id": "A", "slots": [1, 2]},
                {"id": "B", "slots": [1]},
            ],
        }, "YES"),
        Demo({
            "items": [
                {"id": "A", "slots": [1]},
                {"id": "B", "slots": [1]},
            ],
        }, "NO"),
    )
    instructions = (
        "Assign every item to one distinct slot from its slots list. "
        "Return YES if a complete distinct matching exists; otherwise return NO."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "distinct_slot_match"
    assert result.program.run({
        "items": [
            {"id": "X", "slots": ["red", "blue"]},
            {"id": "Y", "slots": ["blue"]},
        ],
    }) == "YES"


def test_distinct_slot_match_builds_permutation_loop() -> None:
    demos = (Demo({
        "items": [
            {"id": "A", "slots": [1, 2]},
            {"id": "B", "slots": [1]},
        ],
    }, "YES"),)
    program = Program.parse(PROGRAM_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    changed = [item for item in loops.mandatory if item.kind == LoopKind.MATCHING_PERMUTATION]
    assert changed
    assert all(item.expected == "YES" for item in changed)


def test_distinct_slot_match_proposal_declares_labels() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "bounded augmenting paths",
        "confidence": 0.9,
        "declared_constants": ["YES", "NO"],
    })

    proposals = backend.propose(
        "Return YES when every item has a distinct slot; otherwise return NO.",
        (Demo({"items": [{"id": "A", "slots": [1]}]}, "YES"),),
        ("YES", "NO"),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "distinct_slot_match"


def test_distinct_slot_match_proposal_rejects_undeclared_failure() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "hidden failure label",
        "confidence": 0.9,
        "declared_constants": ["YES"],
    })

    with pytest.raises(ProposalError, match="undeclared constant"):
        backend.propose(
            "Return YES when every item has a distinct slot; otherwise return NO.",
            (Demo({"items": [{"id": "A", "slots": [1]}]}, "YES"),),
            ("YES", "NO"),
        )
