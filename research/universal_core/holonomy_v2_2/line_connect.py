from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]
_MODE_FAMILIES = {
    "horizontal": ("horizontal",),
    "vertical": ("vertical",),
    "orthogonal": ("horizontal", "vertical"),
    "diagonal": ("main_diagonal", "anti_diagonal"),
    "all": ("horizontal", "vertical", "main_diagonal", "anti_diagonal"),
}


def _shape(grid: Grid) -> tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("line connection requires a nonempty grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("line connection requires a rectangular grid")
    return len(grid), width


def _line_key(point: Point, family: str) -> int:
    row, col = point
    if family == "horizontal":
        return row
    if family == "vertical":
        return col
    if family == "main_diagonal":
        return row - col
    if family == "anti_diagonal":
        return row + col
    raise ValueError("unknown line family")


def _segment(first: Point, last: Point, family: str) -> tuple[Point, ...]:
    if family == "horizontal":
        row = first[0]
        return tuple((row, col) for col in range(first[1], last[1] + 1))
    if family == "vertical":
        col = first[1]
        return tuple((row, col) for row in range(first[0], last[0] + 1))
    if family == "main_diagonal":
        return tuple(
            (row, first[1] + (row - first[0]))
            for row in range(first[0], last[0] + 1)
        )
    if family == "anti_diagonal":
        return tuple(
            (row, first[1] - (row - first[0]))
            for row in range(first[0], last[0] + 1)
        )
    raise ValueError("unknown line family")


def _ordered(points: Sequence[Point], family: str) -> list[Point]:
    if family == "horizontal":
        return sorted(points, key=lambda item: item[1])
    return sorted(points, key=lambda item: item[0])


def apply_line_connect(program: Mapping[str, Any], grid: Grid) -> Grid:
    _shape(grid)
    background = int(program["background"])
    mode = str(program["mode"])
    if mode not in _MODE_FAMILIES:
        raise ValueError("unknown line connection mode")

    colors = sorted({cell for row in grid for cell in row if cell != background})
    anchors = {
        color: tuple(
            (row, col)
            for row, values in enumerate(grid)
            for col, cell in enumerate(values)
            if cell == color
        )
        for color in colors
    }

    claims: dict[Point, int] = {}
    for color in colors:
        for family in _MODE_FAMILIES[mode]:
            groups: dict[int, list[Point]] = defaultdict(list)
            for point in anchors[color]:
                groups[_line_key(point, family)].append(point)
            for points in groups.values():
                if len(points) < 2:
                    continue
                ordered = _ordered(points, family)
                for row, col in _segment(ordered[0], ordered[-1], family):
                    existing = grid[row][col]
                    if existing not in (background, color):
                        raise ValueError("line connection color conflict")
                    claimed = claims.get((row, col))
                    if claimed is not None and claimed != color:
                        raise ValueError("line connection color conflict")
                    claims[(row, col)] = color

    output = [list(row) for row in grid]
    for (row, col), color in claims.items():
        output[row][col] = color
    return output


def line_connect_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    for source, target in demos:
        if _shape(source) != _shape(target):
            return (), "NO_SHAPE_PRESERVING_LINE_CONNECT"

    common_backgrounds = {cell for row in demos[0][0] for cell in row}
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)

    programs: list[Program] = []
    for background in sorted(common_backgrounds):
        for mode in _MODE_FAMILIES:
            program = {
                "kind": "same_color_line_connect",
                "background": background,
                "mode": mode,
            }
            predictions: list[Grid] = []
            try:
                predictions = [apply_line_connect(program, source) for source, _ in demos]
            except (KeyError, TypeError, ValueError):
                continue
            if not any(prediction != source for prediction, (source, _) in zip(predictions, demos)):
                continue
            if all(prediction == target for prediction, (_, target) in zip(predictions, demos)):
                programs.append(program)

    if not programs:
        return (), "NO_LINE_CONNECTION"
    return tuple(programs), None
