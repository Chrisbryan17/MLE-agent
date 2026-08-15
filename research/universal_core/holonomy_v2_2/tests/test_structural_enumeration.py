from __future__ import annotations

from research.universal_core.holonomy_v2_2 import (
    component_select,
    panel_combine,
    region_fill,
)


def test_panel_programs_expose_hypotheses_before_fit() -> None:
    demos = (([[1, 0, 9, 2, 0]], [[4, 0]]),)

    programs, reason = panel_combine.panel_programs(demos)

    assert reason is None
    assert len(programs) > len(panel_combine.panel_candidates(demos))
    assert any(item["predicate"] == "xor" for item in programs)


def test_panel_programs_report_target_color_skip() -> None:
    programs, reason = panel_combine.panel_programs((([[1, 0]], [[7, 7]]),))

    assert programs == ()
    assert reason == "TARGET_COLOR_CARDINALITY_NOT_TWO"


def test_region_programs_expose_hypotheses_before_fit() -> None:
    source = [
        [0, 2, 2],
        [2, 0, 2],
        [2, 2, 2],
    ]
    demos = ((source, source),)

    programs, reason = region_fill.region_programs(demos)

    assert reason is None
    assert len(programs) > len(region_fill.region_candidates(demos))
    assert {item["mode"] for item in programs} == {"fill_copy", "highlight", "solidify"}


def test_region_programs_report_missing_background() -> None:
    demos = (
        ([[1, 1], [1, 2]], [[1, 1], [1, 2]]),
        ([[2, 2], [2, 1]], [[2, 2], [2, 1]]),
    )

    programs, reason = region_fill.region_programs(demos)

    assert programs == ()
    assert reason == "NO_BACKGROUND_CANDIDATE"


def test_component_select_programs_expose_hypotheses_before_fit() -> None:
    demos = ((
        [
            [0, 2, 0, 3, 3, 0],
            [0, 2, 0, 3, 3, 0],
            [0, 0, 0, 3, 0, 0],
        ],
        [[3, 3], [3, 3], [3, 0]],
    ),)

    programs, reason = component_select.component_select_programs(demos)

    assert reason is None
    assert len(programs) > len(component_select.component_select_candidates(demos))
    assert {item["selector"] for item in programs} == {"minimum", "maximum"}


def test_component_select_programs_report_missing_background() -> None:
    demos = (
        ([[1, 1], [1, 2]], [[1]]),
        ([[2, 2], [2, 1]], [[2]]),
    )

    programs, reason = component_select.component_select_programs(demos)

    assert programs == ()
    assert reason == "NO_BACKGROUND_CANDIDATE"
