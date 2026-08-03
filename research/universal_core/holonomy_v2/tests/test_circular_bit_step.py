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


CHAR_DATA = {
    "kind": "circular_bit_step",
    "sequence_field": "bits",
    "steps_field": "steps",
    "token_mode": "characters",
    "rule": 90,
}


INTEGER_DATA = {
    **CHAR_DATA,
    "token_mode": "integers",
    "rule": 204,
}


def test_circular_bit_step_applies_elementary_rule() -> None:
    program = Program.parse(CHAR_DATA)

    assert program.run({"bits": "01001", "steps": 1}) == "00110"


def test_circular_bit_step_wraps_the_ring_edges() -> None:
    program = Program.parse(CHAR_DATA)

    assert program.run({"bits": "1000", "steps": 1}) == "0101"


def test_circular_bit_step_supports_multiple_and_zero_steps() -> None:
    program = Program.parse(CHAR_DATA)

    assert program.run({"bits": "1000", "steps": 2}) == "0000"
    assert program.run({"bits": "1010", "steps": 0}) == "1010"


def test_circular_bit_step_preserves_list_and_tuple_forms() -> None:
    program = Program.parse(INTEGER_DATA)

    assert program.run({"bits": [1, 0, 1], "steps": 3}) == [1, 0, 1]
    assert program.run({"bits": (1, 0, 1), "steps": 2}) == (1, 0, 1)


def test_circular_bit_step_rejects_invalid_rule_mode_bits_and_steps() -> None:
    with pytest.raises(ValueError, match="rule"):
        Program.parse({**CHAR_DATA, "rule": 256})
    with pytest.raises(ValueError, match="token mode"):
        Program.parse({**CHAR_DATA, "token_mode": "words"})

    program = Program.parse(CHAR_DATA)
    with pytest.raises(ValueError, match="binary"):
        program.run({"bits": "012", "steps": 1})
    with pytest.raises(ValueError, match="nonnegative"):
        program.run({"bits": "010", "steps": -1})


def test_circular_bit_step_respects_state_and_step_bounds() -> None:
    program = Program.parse(CHAR_DATA)

    with pytest.raises(BudgetExceeded, match="bit count"):
        program.run(
            {"bits": "010", "steps": 1},
            EngineLimits(max_state_count=2),
        )
    with pytest.raises(BudgetExceeded, match="step count"):
        program.run(
            {"bits": "01", "steps": 2},
            EngineLimits(max_steps=1),
        )


def test_induces_circular_bit_step_from_explicit_rule() -> None:
    demos = (
        Demo({"bits": "1000", "steps": 1}, "0101"),
        Demo({"bits": "1000", "steps": 2}, "0000"),
        Demo({"bits": "1010", "steps": 0}, "1010"),
    )
    instructions = (
        "Apply elementary cellular automaton rule 90 to bits on a circular ring "
        "for the given number of steps. Return the resulting bits."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "circular_bit_step"
    assert result.program.run({"bits": "01001", "steps": 1}) == "00110"


def test_circular_bit_step_builds_rotation_loop() -> None:
    demos = (Demo({"bits": "1000", "steps": 1}, "0101"),)
    program = Program.parse(CHAR_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    rotated = [item for item in loops.mandatory if item.kind == LoopKind.BIT_ROTATION_EQUIVARIANCE]
    assert rotated
    assert all(item.expected == "1010" for item in rotated)


def test_circular_bit_step_proposal_declares_rule() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": CHAR_DATA,
        "rationale": "bounded circular elementary automaton",
        "confidence": 0.9,
        "declared_constants": [90],
    })

    proposals = backend.propose(
        "Apply circular elementary rule 90.",
        (Demo({"bits": "1000", "steps": 1}, "0101"),),
        (90,),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "circular_bit_step"


def test_circular_bit_step_proposal_rejects_undeclared_rule() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": CHAR_DATA,
        "rationale": "hidden rule",
        "confidence": 0.9,
        "declared_constants": [],
    })

    with pytest.raises(ProposalError, match="undeclared constant"):
        backend.propose(
            "Apply circular elementary rule 90.",
            (Demo({"bits": "1000", "steps": 1}, "0101"),),
            (90,),
        )
