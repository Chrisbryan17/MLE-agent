from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]

_PREDICATES = (
    "or",
    "and",
    "xor",
    "equal_foreground",
    "left_only",
    "right_only",
)


def _split(grid: Grid, axis: str, gap: int) -> tuple[Grid, Grid]:
    height = len(grid)
    width = len(grid[0])
    if axis == "vertical":
        if (width - gap) % 2:
            raise ValueError("vertical panels must have equal width")
        panel_width = (width - gap) // 2
        if panel_width < 1:
            raise ValueError("vertical panel width must be positive")
        left = [row[:panel_width] for row in grid]
        right = [row[panel_width + gap :] for row in grid]
        return left, right
    if axis == "horizontal":
        if (height - gap) % 2:
            raise ValueError("horizontal panels must have equal height")
        panel_height = (height - gap) // 2
        if panel_height < 1:
            raise ValueError("horizontal panel height must be positive")
        return grid[:panel_height], grid[panel_height + gap :]
    raise ValueError("unknown panel axis")


def _predicate(name: str, left: int, right: int, background: int) -> bool:
    left_foreground = left != background
    right_foreground = right != background
    if name == "or":
        return left_foreground or right_foreground
    if name == "and":
        return left_foreground and right_foreground
    if name == "xor":
        return left_foreground != right_foreground
    if name == "equal_foreground":
        return left_foreground == right_foreground
    if name == "left_only":
        return left_foreground and not right_foreground
    if name == "right_only":
        return right_foreground and not left_foreground
    raise ValueError("unknown panel predicate")


def apply_panel(program: Mapping[str, Any], grid: Grid) -> Grid:
    left, right = _split(grid, str(program["axis"]), int(program["gap"]))
    if len(left) != len(right) or len(left[0]) != len(right[0]):
        raise ValueError("panel shapes differ")
    background = int(program["background"])
    true_color = int(program["true_color"])
    false_color = int(program["false_color"])
    predicate = str(program["predicate"])
    return [
        [
            true_color
            if _predicate(predicate, left[row][col], right[row][col], background)
            else false_color
            for col in range(len(left[0]))
        ]
        for row in range(len(left))
    ]


def _fits(program: Program, demos: Sequence[tuple[Grid, Grid]]) -> bool:
    try:
        return all(apply_panel(program, source) == target for source, target in demos)
    except (KeyError, TypeError, ValueError):
        return False


def _modal_color(grid: Grid) -> int:
    counts = Counter(cell for row in grid for cell in row)
    highest = max(counts.values())
    return min(color for color, count in counts.items() if count == highest)


def _background_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[int, ...]:
    backgrounds = {0}
    modal_colors = {_modal_color(source) for source, _ in demos}
    if len(modal_colors) == 1:
        backgrounds.update(modal_colors)
    return tuple(sorted(backgrounds))


def panel_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    target_colors = sorted(
        {cell for _, target in demos for row in target for cell in row}
    )
    if len(target_colors) != 2:
        return (), "TARGET_COLOR_CARDINALITY_NOT_TWO"
    programs: list[Program] = []
    for axis in ("vertical", "horizontal"):
        for gap in (0, 1, 2):
            for background in _background_candidates(demos):
                for predicate in _PREDICATES:
                    for true_color, false_color in (
                        (target_colors[0], target_colors[1]),
                        (target_colors[1], target_colors[0]),
                    ):
                        programs.append({
                            "kind": "panel_boolean_combine",
                            "axis": axis,
                            "gap": gap,
                            "background": background,
                            "predicate": predicate,
                            "true_color": true_color,
                            "false_color": false_color,
                        })
    if not programs:
        return (), "NO_STRUCTURAL_PROGRAM"
    return tuple(programs), None


def panel_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[Program, ...]:
    programs, _ = panel_programs(demos)
    return tuple(program for program in programs if _fits(program, demos))
