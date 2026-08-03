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
    "kind": "cyclic_skip_step",
    "cycle_field": "cycle",
    "start_field": "start",
    "steps_field": "steps",
    "blocked_field": "blocked",
}


def test_cyclic_skip_step_skips_blocked_positions_and_wraps() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "cycle": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "start": "Fri",
        "steps": 1,
        "blocked": ["Sat", "Sun"],
    }) == "Mon"
    assert program.run({
        "cycle": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "start": "Thu",
        "steps": 4,
        "blocked": ["Sat", "Sun"],
    }) == "Wed"


def test_cyclic_skip_step_zero_steps_preserves_start() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "cycle": ["A", "B", "C"],
        "start": "B",
        "steps": 0,
        "blocked": ["B"],
    }) == "B"


def test_cyclic_skip_step_supports_structured_cycle_values() -> None:
    program = Program.parse(PROGRAM_DATA)
    first = {"day": 1}
    second = {"day": 2}
    third = {"day": 3}

    assert program.run({
        "cycle": [first, second, third],
        "start": first,
        "steps": 1,
        "blocked": [second],
    }) == third


def test_cyclic_skip_step_rejects_duplicate_cycle_and_unknown_values() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(ValueError, match="duplicate cycle value"):
        program.run({
            "cycle": ["A", "B", "A"],
            "start": "A",
            "steps": 1,
            "blocked": [],
        })
    with pytest.raises(ValueError, match="start is not in cycle"):
        program.run({
            "cycle": ["A", "B"],
            "start": "C",
            "steps": 1,
            "blocked": [],
        })
    with pytest.raises(ValueError, match="blocked value is not in cycle"):
        program.run({
            "cycle": ["A", "B"],
            "start": "A",
            "steps": 1,
            "blocked": ["C"],
        })


def test_cyclic_skip_step_rejects_all_blocked_for_positive_steps() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(ValueError, match="allowed cycle value"):
        program.run({
            "cycle": ["A", "B"],
            "start": "A",
            "steps": 1,
            "blocked": ["A", "B"],
        })


def test_cyclic_skip_step_rejects_invalid_steps_and_collections() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(ValueError, match="nonnegative"):
        program.run({"cycle": ["A"], "start": "A", "steps": -1, "blocked": []})
    with pytest.raises(TypeError, match="cycle must be a sequence"):
        program.run({"cycle": "ABC", "start": "A", "steps": 1, "blocked": []})
    with pytest.raises(TypeError, match="blocked must be a sequence"):
        program.run({"cycle": ["A"], "start": "A", "steps": 1, "blocked": "A"})


def test_cyclic_skip_step_respects_cycle_and_step_bounds() -> None:
    program = Program.parse(PROGRAM_DATA)

    with pytest.raises(BudgetExceeded, match="cycle length"):
        program.run(
            {"cycle": ["A", "B"], "start": "A", "steps": 1, "blocked": []},
            EngineLimits(max_state_count=1),
        )
    with pytest.raises(BudgetExceeded, match="step count"):
        program.run(
            {"cycle": ["A"], "start": "A", "steps": 2, "blocked": []},
            EngineLimits(max_steps=1),
        )


def test_induces_cyclic_skip_step_from_explicit_policy() -> None:
    demos = (
        Demo({
            "cycle": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "start": "Fri",
            "steps": 1,
            "blocked": ["Sat", "Sun"],
        }, "Mon"),
        Demo({
            "cycle": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "start": "Mon",
            "steps": 3,
            "blocked": ["Wed"],
        }, "Fri"),
    )
    instructions = (
        "Move forward around cycle from start by the given number of allowed steps. "
        "Skip every value listed in blocked and wrap around the cycle."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "cyclic_skip_step"
    assert result.program.run({
        "cycle": [1, 2, 3, 4],
        "start": 4,
        "steps": 2,
        "blocked": [1],
    }) == 3


def test_cyclic_skip_step_builds_cycle_rotation_loop() -> None:
    demos = (Demo({
        "cycle": ["A", "B", "C", "D"],
        "start": "D",
        "steps": 2,
        "blocked": ["A"],
    }, "C"),)
    program = Program.parse(PROGRAM_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    rotated = [item for item in loops.mandatory if item.kind == LoopKind.CYCLE_ROTATION]
    assert rotated
    assert all(item.expected == "C" for item in rotated)


def test_cyclic_skip_step_proposal_needs_no_semantic_constants() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "bounded cyclic skip stepping",
        "confidence": 0.9,
        "declared_constants": [],
    })

    proposals = backend.propose(
        "Move around the cycle while skipping blocked values.",
        (Demo({
            "cycle": ["A", "B", "C"],
            "start": "A",
            "steps": 1,
            "blocked": ["B"],
        }, "C"),),
        (),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "cyclic_skip_step"


def test_cyclic_skip_step_proposal_rejects_extra_program_fields() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": {**PROGRAM_DATA, "hidden": "X"},
        "rationale": "extra hidden field",
        "confidence": 0.9,
        "declared_constants": [],
    })

    with pytest.raises(ProposalError, match="extra node fields"):
        backend.propose(
            "Move around the cycle while skipping blocked values.",
            (Demo({
                "cycle": ["A", "B"],
                "start": "A",
                "steps": 1,
                "blocked": [],
            }, "B"),),
            (),
        )
