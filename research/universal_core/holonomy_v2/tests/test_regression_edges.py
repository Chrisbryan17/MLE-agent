from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.search import search_candidates
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_instruction_filter_applies_to_each_numeric_field() -> None:
    demos = (
        Demo([
            {"glyph": "a", "measure": 119},
            {"glyph": "b", "measure": 103},
            {"glyph": "c", "measure": -674},
            {"glyph": "d", "measure": 219},
        ], 3),
        Demo([
            {"glyph": "e", "measure": -219},
            {"glyph": "f", "measure": 400},
            {"glyph": "g", "measure": 393},
        ], 2),
    )
    result = search_candidates(
        "Report how many entries have a measure no less than 7.",
        demos,
        SearchConfig(),
    )
    assert result.program is not None
    assert result.program.run([{"glyph": "x", "measure": 7}, {"glyph": "y", "measure": 6}]) == 1


def test_instruction_predicate_removes_integer_equivalent_ambiguity() -> None:
    demos = (
        Demo([
            {"charge": 21, "payload": 35},
            {"charge": 9, "payload": 50},
            {"charge": 10, "payload": 4},
        ], 39),
        Demo([
            {"charge": 2, "payload": 20},
            {"charge": 25, "payload": -10},
        ], -10),
    )
    result = search_candidates(
        "Among entries whose charge is at least 10, sum the payload values.",
        demos,
        SearchConfig(),
    )
    assert result.program is not None
    assert result.program.to_data()["parts"][0]["comparison"] == ">="
    assert result.program.to_data()["parts"][0]["value"] == 10


def test_priority_labels_can_come_from_instruction_when_examples_share_one_label() -> None:
    demos = tuple(
        Demo(item, "DENY")
        for item in (
            {"charter": False, "copper": False, "ivory": True, "licensed": False, "rescue": False, "storm": False, "witness": False},
            {"charter": False, "copper": False, "ivory": False, "licensed": True, "rescue": False, "storm": False, "witness": True},
            {"charter": False, "copper": False, "ivory": False, "licensed": False, "rescue": False, "storm": True, "witness": False},
            {"charter": False, "copper": False, "ivory": False, "licensed": False, "rescue": True, "storm": False, "witness": False},
            {"charter": True, "copper": False, "ivory": False, "licensed": False, "rescue": False, "storm": False, "witness": False},
        )
    )
    text = (
        "Apply these rules in priority order. During a storm, deny unless rescue is true. "
        "Otherwise, charter together with witness allows. Otherwise, licensed together with "
        "either copper or ivory allows. All remaining cases deny. Return ALLOW or DENY."
    )
    result = search_candidates(text, demos, SearchConfig())
    assert result.program is not None
    assert result.program.run({
        "charter": True, "witness": True, "storm": False, "rescue": False,
        "licensed": False, "copper": False, "ivory": False,
    }) == "ALLOW"
