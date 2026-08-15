from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]
_DIRECTION = {
    "N": (-1, 0),
    "S": (1, 0),
    "W": (0, -1),
    "E": (0, 1),
    "NW": (-1, -1),
    "NE": (-1, 1),
    "SW": (1, -1),
    "SE": (1, 1),
}
_MODE_DIRECTIONS = {
    "up": ("N",),
    "down": ("S",),
    "left": ("W",),
    "right": ("E",),
    "vertical": ("N", "S"),
    "horizontal": ("W", "E"),
    "orthogonal": ("N", "S", "W", "E"),
    "diagonal": ("NW", "NE", "SW", "SE"),
    "all": ("N", "S", "W", "E", "NW", "NE", "SW", "SE"),
}


def _shape(grid: Grid) -> tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("ray extension requires a nonempty grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("ray extension requires a rectangular grid")
    return len(grid), width


def apply_ray_extend(program: Mapping[str, Any], grid: Grid) -> Grid:
    height, width = _shape(grid)
    background = int(program["background"])
    mode = str(program["mode"])
    if mode not in _MODE_DIRECTIONS:
        raise ValueError("unknown ray extension mode")

    anchors = tuple(
        (row, col, grid[row][col])
        for row in range(height)
        for col in range(width)
        if grid[row][col] != background
    )
    claims: dict[Point, int] = {}
    for row, col, color in anchors:
        for direction in _MODE_DIRECTIONS[mode]:
            delta_row, delta_col = _DIRECTION[direction]
            target_row = row + delta_row
            target_col = col + delta_col
            while 0 <= target_row < height and 0 <= target_col < width:
                existing = grid[target_row][target_col]
                if existing not in (background, color):
                    raise ValueError("ray extension color conflict")
                point = (target_row, target_col)
                claimed = claims.get(point)
                if claimed is not None and claimed != color:
                    raise ValueError("ray extension color conflict")
                claims[point] = color
                target_row += delta_row
                target_col += delta_col

    output = [list(row) for row in grid]
    for (row, col), color in claims.items():
        output[row][col] = color
    return output


def ray_extend_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    for source, target in demos:
        if _shape(source) != _shape(target):
            return (), "NO_SHAPE_PRESERVING_RAY_EXTENSION"

    common_backgrounds = {cell for row in demos[0][0] for cell in row}
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)

    programs: list[Program] = []
    for background in sorted(common_backgrounds):
        for mode in _MODE_DIRECTIONS:
            program = {
                "kind": "anchor_ray_extend",
                "background": background,
                "mode": mode,
            }
            try:
                predictions = [apply_ray_extend(program, source) for source, _ in demos]
            except (KeyError, TypeError, ValueError):
                continue
            if not any(prediction != source for prediction, (source, _) in zip(predictions, demos)):
                continue
            if all(prediction == target for prediction, (_, target) in zip(predictions, demos)):
                programs.append(program)

    if not programs:
        return (), "NO_RAY_EXTENSION"
    return tuple(programs), None
