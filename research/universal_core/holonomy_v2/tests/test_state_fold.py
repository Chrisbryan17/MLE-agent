from dataclasses import dataclass
from typing import Any

import pytest

from universal_core.holonomy_v2.loops import LoopKind, build_loops
from universal_core.holonomy_v2.grammar_ext import build_task_grammar_extended
from universal_core.holonomy_v2.program import Program
from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


TRANSITIONS = [
    {"state": "idle", "action": "arm", "next": "ready"},
    {"state": "ready", "action": "launch", "next": "active"},
    {"state": "ready", "action": "reset", "next": "idle"},
    {"state": "active", "action": "reset", "next": "idle"},
]


def test_state_fold_executes_a_bounded_transition_system() -> None:
    program = Program.parse({
        "kind": "state_fold",
        "state_field": "mode",
        "actions_field": "commands",
        "transitions": TRANSITIONS,
    })

    assert program.run({"mode": "idle", "commands": ["arm", "launch", "reset"]}) == "idle"


def test_state_fold_rejects_conflicting_transitions() -> None:
    with pytest.raises(ValueError, match="conflicting transition"):
        Program.parse({
            "kind": "state_fold",
            "state_field": "mode",
            "actions_field": "commands",
            "transitions": [
                {"state": "idle", "action": "arm", "next": "ready"},
                {"state": "idle", "action": "arm", "next": "active"},
            ],
        })


def test_induces_state_fold_from_instruction_transitions() -> None:
    demos = (
        Demo({"mode": "idle", "commands": ["arm"]}, "ready"),
        Demo({"mode": "ready", "commands": ["launch"]}, "active"),
        Demo({"mode": "active", "commands": ["reset", "arm"]}, "ready"),
    )
    instructions = (
        "Apply every command in order to the current mode. Transitions: "
        "idle + arm -> ready; ready + launch -> active; ready + reset -> idle; "
        "active + reset -> idle. Return the final mode."
    )

    result = search_candidates(instructions, demos, SearchConfig())

    assert result.abstention is None
    assert result.program is not None
    assert result.program.to_data()["kind"] == "state_fold"
    assert result.program.run({"mode": "ready", "commands": ["reset", "arm", "launch"]}) == "active"


def test_state_fold_builds_a_mandatory_cycle_loop() -> None:
    demos = (Demo({"mode": "idle", "commands": ["arm"]}, "ready"),)
    program = Program.parse({
        "kind": "state_fold",
        "state_field": "mode",
        "actions_field": "commands",
        "transitions": TRANSITIONS,
    })
    grammar = build_task_grammar_extended("", demos, SearchConfig())

    loops = build_loops(program, demos, grammar)

    cycles = [item for item in loops.mandatory if item.kind == LoopKind.STATE_CYCLE]
    assert cycles
    assert all(item.expected == item.input_value["mode"] for item in cycles)
