from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]
_TRANSFORM_ORDER = (
    "vertical",
    "horizontal",
    "rotate_180",
    "main_diagonal",
    "anti_diagonal",
)


def _shape(grid: Grid) -> tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("symmetry completion requires a nonempty grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("symmetry completion requires a rectangular grid")
    return len(grid), width


def _reflect(point: Point, height: int, width: int, transform: str) -> Point:
    row, col = point
    if transform == "vertical":
        return row, width - 1 - col
    if transform == "horizontal":
        return height - 1 - row, col
    if transform == "rotate_180":
        return height - 1 - row, width - 1 - col
    if transform == "main_diagonal":
        if height != width:
            raise ValueError("diagonal symmetry requires a square grid")
        return col, row
    if transform == "anti_diagonal":
        if height != width:
            raise ValueError("diagonal symmetry requires a square grid")
        return width - 1 - col, height - 1 - row
    raise ValueError("unknown symmetry transform")


def apply_symmetry_complete(program: Mapping[str, Any], grid: Grid) -> Grid:
    height, width = _shape(grid)
    background = int(program["background"])
    transform = str(program["transform"])
    if transform not in _TRANSFORM_ORDER:
        raise ValueError("unknown symmetry transform")

    anchors = tuple(
        (row, col, grid[row][col])
        for row in range(height)
        for col in range(width)
        if grid[row][col] != background
    )
    claims: dict[Point, int] = {}
    for row, col, color in anchors:
        reflected = _reflect((row, col), height, width, transform)
        target_row, target_col = reflected
        existing = grid[target_row][target_col]
        if existing not in (background, color):
            raise ValueError("symmetry completion color conflict")
        claimed = claims.get(reflected)
        if claimed is not None and claimed != color:
            raise ValueError("symmetry completion color conflict")
        claims[reflected] = color

    output = [list(row) for row in grid]
    for (row, col), color in claims.items():
        output[row][col] = color
    return output


def symmetry_complete_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    for source, target in demos:
        if _shape(source) != _shape(target):
            return (), "NO_SHAPE_PRESERVING_SYMMETRY"

    common_backgrounds = {cell for row in demos[0][0] for cell in row}
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)

    programs: list[Program] = []
    for background in sorted(common_backgrounds):
        for transform in _TRANSFORM_ORDER:
            program = {
                "kind": "reflective_symmetry_complete",
                "background": background,
                "transform": transform,
            }
            try:
                predictions = [apply_symmetry_complete(program, source) for source, _ in demos]
            except (KeyError, TypeError, ValueError):
                continue
            if not any(prediction != source for prediction, (source, _) in zip(predictions, demos)):
                continue
            if all(prediction == target for prediction, (_, target) in zip(predictions, demos)):
                programs.append(program)

    if not programs:
        return (), "NO_REFLECTIVE_SYMMETRY_COMPLETION"
    return tuple(programs), None
