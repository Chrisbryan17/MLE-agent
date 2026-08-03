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
    "kind": "ray_first_hit",
    "origin_field": "origin",
    "direction_field": "direction",
    "objects_field": "objects",
    "id_field": "id",
    "min_field": "min",
    "max_field": "max",
    "tie_policy": "lexicographic",
    "default": "NONE",
}


def test_ray_first_hit_returns_nearest_axis_aligned_box() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "origin": [0, 0],
        "direction": [1, 0],
        "objects": [
            {"id": "A", "min": [5, -1], "max": [6, 1]},
            {"id": "B", "min": [2, -1], "max": [3, 1]},
        ],
    }) == "B"


def test_ray_first_hit_ignores_parallel_misses_and_uses_default() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "origin": [0, 0],
        "direction": [1, 0],
        "objects": [
            {"id": "A", "min": [2, 2], "max": [3, 3]},
            {"id": "B", "min": [-3, -1], "max": [-2, 1]},
        ],
    }) == "NONE"


def test_ray_first_hit_counts_origin_inside_as_zero_distance() -> None:
    program = Program.parse(PROGRAM_DATA)

    assert program.run({
        "origin": [0, 0, 0],
        "direction": [1, 1, 1],
        "objects": [
            {"id": "inside", "min": [-1, -1, -1], "max": [1, 1, 1]},
            {"id": "later", "min": [2, 2, 2], "max": [3, 3, 3]},
        ],
    }) == "inside"


def test_ray_first_hit_applies_deterministic_tie_policy() -> None:
    objects = [
        {"id": "B", "min": [2, -1], "max": [3, 1]},
        {"id": "A", "min": [2, -1], "max": [3, 1]},
    ]

    assert Program.parse(PROGRAM_DATA).run({
        "origin": [0, 0], "direction": [1, 0], "objects": objects,
    }) == "A"
    assert Program.parse({**PROGRAM_DATA, "tie_policy": "first"}).run({
        "origin": [0, 0], "direction": [1, 0], "objects": objects,
    }) == "B"


def test_ray_first_hit_rejects_zero_direction_and_invalid_policy() -> None:
    with pytest.raises(ValueError, match="tie policy"):
        Program.parse({**PROGRAM_DATA, "tie_policy": "random"})

    program = Program.parse(PROGRAM_DATA)
    with pytest.raises(ValueError, match="nonzero"):
        program.run({
            "origin": [0, 0],
            "direction": [0, 0],
            "objects": [],
        })


def test_ray_first_hit_respects_object_bound() -> None:
    program = Program.parse(PROGRAM_DATA)
    box = {"id": "A", "min": [1, -1], "max": [2, 1]}

    with pytest.raises(BudgetExceeded, match="object count"):
        program.run(
            {"origin": [0, 0], "direction": [1, 0], "objects": [box, box]},
            EngineLimits(max_state_count=1),
        )


def test_induces_ray_first_hit_from_explicit_geometry_policy() -> None:
    demos = (
        Demo({
            "origin": [0, 0],
            "direction": [1, 0],
            "objects": [
                {"id": "A", "min": [4, -1], "max": [5, 1]},
                {"id": "B", "min": [2, -1], "max": [3, 1]},
            ],
        }, "B"),
        Demo({
            "origin": [0, 0],
            "direction": [0, 1],
            "objects": [
                {"id": "A", "min": [-1, 3], "max": [1, 4]},
                {"id": "B", "min": [2, 1], "max": [3, 2]},
            ],
        }, "A"),
        Demo({
            "origin": [0, 0],
            "direction": [1, 0],
            "objects": [
                {"id": "A", "min": [2, 2], "max": [3, 3]},
            ],
        }, "NONE"),
    )
    instructions = (
        "Cast a ray from origin in direction. Each object has id, min, and max coordinates "
        "for an axis-aligned box. Return the id of the first box hit. Break ties "
        "lexicographically; otherwise return NONE."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "ray_first_hit"
    assert result.program.run({
        "origin": [0, 0],
        "direction": [1, 1],
        "objects": [
            {"id": "far", "min": [4, 4], "max": [5, 5]},
            {"id": "near", "min": [2, 2], "max": [3, 3]},
        ],
    }) == "near"


def test_ray_first_hit_builds_direction_scale_loop() -> None:
    demos = (Demo({
        "origin": [0, 0],
        "direction": [1, 0],
        "objects": [
            {"id": "A", "min": [2, -1], "max": [3, 1]},
        ],
    }, "A"),)
    program = Program.parse(PROGRAM_DATA)
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    scaled = [item for item in loops.mandatory if item.kind == LoopKind.RAY_DIRECTION_SCALE]
    assert scaled
    assert all(item.expected == "A" for item in scaled)


def test_ray_first_hit_proposal_declares_default() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "exact slab intersection",
        "confidence": 0.9,
        "declared_constants": ["NONE"],
    })

    proposals = backend.propose(
        "Return the first box hit by the ray.",
        (Demo({
            "origin": [0, 0],
            "direction": [1, 0],
            "objects": [{"id": "A", "min": [1, -1], "max": [2, 1]}],
        }, "A"),),
        ("NONE",),
    )

    assert len(proposals) == 1
    assert proposals[0].program.to_data()["kind"] == "ray_first_hit"


def test_ray_first_hit_proposal_rejects_undeclared_default() -> None:
    backend = JsonProposalBackend(lambda request: {
        "program": PROGRAM_DATA,
        "rationale": "hidden fallback",
        "confidence": 0.9,
        "declared_constants": [],
    })

    with pytest.raises(ProposalError, match="undeclared constant"):
        backend.propose(
            "Return the first box hit by the ray.",
            (Demo({
                "origin": [0, 0],
                "direction": [1, 0],
                "objects": [{"id": "A", "min": [1, -1], "max": [2, 1]}],
            }, "A"),),
            ("NONE",),
        )
