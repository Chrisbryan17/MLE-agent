from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]
Component = tuple[Point, ...]


def _steps(connectivity: int) -> tuple[Point, ...]:
    orthogonal: tuple[Point, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
    if connectivity == 4:
        return orthogonal
    if connectivity == 8:
        return orthogonal + ((1, 1), (1, -1), (-1, 1), (-1, -1))
    raise ValueError("marker connectivity must be four or eight")


def _components(grid: Grid, background: int, connectivity: int) -> tuple[Component, ...]:
    height = len(grid)
    width = len(grid[0])
    seen: set[Point] = set()
    found: list[Component] = []
    for row in range(height):
        for col in range(width):
            point = (row, col)
            if point in seen or grid[row][col] == background:
                continue
            color = grid[row][col]
            pending = [point]
            seen.add(point)
            cells: list[Point] = []
            while pending:
                current = pending.pop()
                cells.append(current)
                for row_step, col_step in _steps(connectivity):
                    next_row = current[0] + row_step
                    next_col = current[1] + col_step
                    next_point = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_point in seen or grid[next_row][next_col] != color:
                        continue
                    seen.add(next_point)
                    pending.append(next_point)
            found.append(tuple(sorted(cells)))
    return tuple(found)


def apply_marker_recolor(program: Mapping[str, Any], grid: Grid) -> Grid:
    background = int(program["background"])
    connectivity = int(program["connectivity"])
    components = _components(grid, background, connectivity)
    singleton_components = [item for item in components if len(item) == 1]
    if len(singleton_components) != 1:
        raise ValueError("marker recolor requires exactly one singleton marker")
    marker = singleton_components[0][0]
    foreground_count = sum(
        1
        for row in grid
        for cell in row
        if cell != background
    )
    if foreground_count <= 1:
        raise ValueError("marker recolor requires another foreground cell")
    marker_color = grid[marker[0]][marker[1]]
    output = deepcopy(grid)
    for row_index, row in enumerate(grid):
        for col_index, cell in enumerate(row):
            point = (row_index, col_index)
            if point == marker:
                output[row_index][col_index] = background
            elif cell != background:
                output[row_index][col_index] = marker_color
    return output


def _background_candidates(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[int, ...]:
    common = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common.intersection_update(cell for row in source for cell in row)
    return tuple(sorted(common))


def marker_recolor_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    backgrounds = _background_candidates(demos)
    if not backgrounds:
        return (), "NO_BACKGROUND_CANDIDATE"
    programs = tuple(
        {
            "kind": "marker_recolor",
            "background": background,
            "connectivity": connectivity,
        }
        for background in backgrounds
        for connectivity in (4, 8)
    )
    return programs, None
