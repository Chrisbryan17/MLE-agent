from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
_DIRECTION_ORDER = ("up", "down", "left", "right")


def _shape(grid: Grid) -> tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("gravity compaction requires a nonempty grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("gravity compaction requires a rectangular grid")
    return len(grid), width


def apply_gravity_compact(program: Mapping[str, Any], grid: Grid) -> Grid:
    height, width = _shape(grid)
    background = int(program["background"])
    direction = str(program["direction"])
    if direction not in _DIRECTION_ORDER:
        raise ValueError("unknown gravity direction")

    if direction in ("left", "right"):
        output: Grid = []
        for source_row in grid:
            values = [cell for cell in source_row if cell != background]
            padding = [background] * (width - len(values))
            output.append(values + padding if direction == "left" else padding + values)
        return output

    output = [[background for _ in range(width)] for _ in range(height)]
    for col in range(width):
        values = [grid[row][col] for row in range(height) if grid[row][col] != background]
        start = 0 if direction == "up" else height - len(values)
        for offset, value in enumerate(values):
            output[start + offset][col] = value
    return output


def gravity_compact_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    for source, target in demos:
        if _shape(source) != _shape(target):
            return (), "NO_SHAPE_PRESERVING_GRAVITY"

    common_backgrounds = {cell for row in demos[0][0] for cell in row}
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)

    programs: list[Program] = []
    for background in sorted(common_backgrounds):
        for direction in _DIRECTION_ORDER:
            program = {
                "kind": "axis_gravity_compact",
                "background": background,
                "direction": direction,
            }
            predictions = [apply_gravity_compact(program, source) for source, _ in demos]
            if not any(prediction != source for prediction, (source, _) in zip(predictions, demos)):
                continue
            if all(prediction == target for prediction, (_, target) in zip(predictions, demos)):
                programs.append(program)

    if not programs:
        return (), "NO_GRAVITY_COMPACTION"
    return tuple(programs), None
