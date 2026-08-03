from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_induces_phase_dependent_symbol_program() -> None:
    demos = (
        Demo({"left": "te", "phase": 1, "right": "mi"}, "te"),
        Demo({"left": "mi", "phase": 2, "right": "mi"}, "te"),
        Demo({"left": "zu", "phase": 0, "right": "ro"}, "ro"),
    )
    text = (
        "Symbols cycle in this order: ka, zu, mi, te, ro. Convert left and right to their "
        "zero-based cycle positions. Add left + 2*right + phase, reduce modulo 5, and return "
        "the symbol at that position."
    )
    result = search_candidates(text, demos, SearchConfig())
    assert result.program is not None
    assert result.program.run({"left": "ka", "right": "zu", "phase": 0}) == "mi"


def test_induces_prioritized_boolean_rules() -> None:
    demos = (
        Demo({"charter": False, "copper": False, "ivory": True, "licensed": False, "rescue": False, "storm": False, "witness": False}, "DENY"),
        Demo({"charter": True, "copper": False, "ivory": False, "licensed": False, "rescue": False, "storm": False, "witness": True}, "ALLOW"),
        Demo({"charter": True, "copper": False, "ivory": False, "licensed": False, "rescue": False, "storm": True, "witness": True}, "DENY"),
        Demo({"charter": False, "copper": True, "ivory": False, "licensed": True, "rescue": False, "storm": False, "witness": False}, "ALLOW"),
        Demo({"charter": False, "copper": False, "ivory": False, "licensed": False, "rescue": True, "storm": True, "witness": False}, "DENY"),
    )
    text = (
        "Apply these rules in priority order. During a storm, deny unless rescue is true. "
        "Otherwise, charter together with witness allows. Otherwise, licensed together with "
        "either copper or ivory allows. All remaining cases deny. Return ALLOW or DENY."
    )
    result = search_candidates(text, demos, SearchConfig())
    assert result.program is not None
    assert result.program.run({"storm": False, "rescue": False, "charter": False, "witness": False, "licensed": True, "copper": False, "ivory": True}) == "ALLOW"


def test_induces_grid_transition_count() -> None:
    demos = (
        Demo({"board": [".B..", ".AB.", "AA.A", "B.A."], "player": "A"}, 1),
        Demo({"board": ["....", "B..A", "..AB", "B..."], "player": "B"}, 2),
    )
    text = (
        "On the 4x4 board, a legal move jumps one of the player's pieces exactly two squares "
        "orthogonally over one adjacent opponent piece into an empty dot. Count all legal moves "
        "for the named player."
    )
    result = search_candidates(text, demos, SearchConfig())
    assert result.program is not None
    assert result.program.run({"board": ["AB..", "....", "....", "...."], "player": "A"}) == 1


def test_induces_bounded_resource_plan() -> None:
    demos = (
        Demo({
            "jobs": [
                {"duration": 7, "id": "j0-0", "machine": "M1"},
                {"duration": 1, "id": "j0-1", "machine": "M2"},
                {"duration": 1, "id": "j0-2", "machine": "M1"},
                {"duration": 3, "id": "j0-3", "machine": "M2"},
            ],
            "precedence": [["j0-1", "j0-0"], ["j0-0", "j0-3"]],
        }, 11),
        Demo({
            "jobs": [
                {"duration": 2, "id": "j1-0", "machine": "M2"},
                {"duration": 7, "id": "j1-1", "machine": "M1"},
                {"duration": 4, "id": "j1-2", "machine": "M1"},
                {"duration": 6, "id": "j1-3", "machine": "M2"},
                {"duration": 2, "id": "j1-4", "machine": "M1"},
            ],
            "precedence": [["j1-0", "j1-4"], ["j1-3", "j1-1"], ["j1-1", "j1-2"]],
        }, 19),
    )
    text = (
        "Each job has a duration and requires one named machine. A machine handles at most one "
        "job at a time; jobs are non-preemptive; every precedence pair must be respected. Return "
        "the minimum possible completion time for all jobs."
    )
    result = search_candidates(text, demos, SearchConfig())
    assert result.program is not None
    assert result.program.run(demos[0].input) == 11
