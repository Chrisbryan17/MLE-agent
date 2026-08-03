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


COUNT_DATA = {
    "kind": "integer_span_cover",
    "span_start_field": "start",
    "span_end_field": "end",
    "intervals_field": "intervals",
    "interval_start_field": "start",
    "interval_end_field": "end",
    "mode": "minimum_count",
    "failure": -1,
}


FEASIBLE_DATA = {
    **COUNT_DATA,
    "mode": "feasible",
    "success": "YES",
    "failure": "NO",
}


def test_integer_span_cover_returns_minimum_interval_count() -> None:
    program = Program.parse(COUNT_DATA)

    assert program.run({
        "start": 1,
        "end": 10,
        "intervals": [
            {"start": 1, "end": 4},
            {"start": 3, "end": 8},
            {"start": 8, "end": 10},
            {"start": 5, "end": 6},
        ],
    }) == 3


def test_integer_span_cover_uses_farthest_reach_not_first_interval() -> None:
    program = Program.parse(COUNT_DATA)

    assert program.run({
        "start": 1,
        "end": 8,
        "intervals": [
            {"start": 1, "end": 2},
            {"start": 1, "end": 5},
            {"start": 3, "end": 4},
            {"start": 6, "end": 8},
        ],
    }) == 2


def test_integer_span_cover_detects_integer_gap() -> None:
    program = Program.parse(COUNT_DATA)

    assert program.run({
        "start": 1,
        "end": 6,
        "intervals": [
            {"start": 1, "end": 2},
            {"start": 4, "end": 6},
        ],
    }) == -1


def test_integer_span_cover_treats_touching_integer_ranges_as_contiguous() -> None:
    program = Program.parse(COUNT_DATA)

    assert program.run({
        "start": -2,
        "end": 2,
        "intervals": [
            {"start": -2, "end": 0},
            {"start": 1, "end": 2},
        ],
    }) == 2


def test_integer_span_cover_supports_feasibility_labels() -> None:
    program = Program.parse(FEASIBLE_DATA)

    assert program.run({
        "start": 3,
        "end": 5,
        "intervals": [{"start": 2, "end": 6}],
    }) == "YES"
    assert program.run({
        "start": 3,
        "end": 5,
        "intervals": [{"start": 4, "end": 6}],
    }) == "NO"


def test_integer_span_cover_rejects_invalid_endpoints_and_mode() -> None:
    with pytest.raises(ValueError, match="mode"):
        Program.parse({**COUNT_DATA, "mode": "random"})

    program = Program.parse(COUNT_DATA)
    with pytest.raises(ValueError, match="span start"):
        program.run({"start": 5, "end": 4, "intervals": []})
    with pytest.raises(TypeError, match="integers"):
        program.run({
            "start": 1,
            "end": 3,
            "intervals": [{"start": 1.5, "end": 3}],
        })


def test_integer_span_cover_respects_interval_bound() -> None:
    program = Program.parse(COUNT_DATA)

    with pytest.raises(BudgetExceeded, match="interval count"):
        program.run(
            {
                "start": 1,
                "end": 2,
                "intervals": [
                    {"start": 1, "end": 1},
                    {"start": 2, "end": 2},
                ],
            },
            EngineLimits(max_state_count=1),
        )


def test_induces_integer_span_cover_from_explicit_policy() -> None:
    demos = (
        Demo({
            "start": 1,
            "end": 6,
            "intervals": [
                {"start": 1, "end": 3},
                {"start": 4, "end": 6},
            ],
        }, 2),
        Demo({
            "start": 1,
            "end": 5,
            "intervals": [
                {"start": 1, "end": 2},
                {"start": 4, "end": 5},
            ],
        }, -1),
    )
    instructions = (
        "Cover every integer from start through end using the minimum number of intervals. "
        "Intervals include both endpoints. Return -1 if the span cannot be covered."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "integer_span_cover"
    assert result.program.run({
        "start": 10,
        "end": 15,
        "intervals": [
            {"start": 9, "end": 12},
            {"start": 13, "end": 15},
        ],
    }) == 2


def test_integer_span_cover_builds_translation_loop() -> None:
    demos = (Demo({
        "start": 1,
        "end": 5,
        "intervals": [
            {"start": 1, "end": 2},
            {"start": 3, "end": 5},
        ],
    }, 2),)
    program = Program.parse(COUNT_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    shifted = [item for item in loops.mandatory if item.kind == LoopKind.SPAN_TRANSLATION]
    assert shifted
    assert all(item.expected == 2 for item in shifted)


def test_integer_span_cover_proposal_declares_failure() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": COUNT_DATA,
        "rationale": "bounded inclusive span covering",
        "confidence": 0.9,
        "declared_constants": [-1],
    })

    proposals = backend.propose(
        "Return the minimum interval count or -1.",
        (Demo({
            "start": 1,
            "end": 2,
            "intervals": [{"start": 1, "end": 2}],
        }, 1),),
        (-1,),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "integer_span_cover"


def test_integer_span_cover_proposal_rejects_undeclared_label() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": FEASIBLE_DATA,
        "rationale": "hidden feasibility label",
        "confidence": 0.9,
        "declared_constants": ["YES"],
    })

    with pytest.raises(ProposalError, match="undeclared constant"):
        backend.propose(
            "Return YES when the span is covered; otherwise return NO.",
            (Demo({
                "start": 1,
                "end": 2,
                "intervals": [{"start": 1, "end": 2}],
            }, "YES"),),
            ("YES", "NO"),
        )
