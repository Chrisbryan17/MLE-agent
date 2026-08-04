from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]


def _directions(connectivity: int) -> tuple[Point, ...]:
    steps: tuple[Point, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
    if connectivity == 8:
        return steps + ((1, 1), (1, -1), (-1, 1), (-1, -1))
    if connectivity == 4:
        return steps
    raise ValueError("region connectivity must be four or eight")


def _exterior_background(grid: Grid, background: int, connectivity: int) -> set[Point]:
    height = len(grid)
    width = len(grid[0])
    pending: list[Point] = []
    seen: set[Point] = set()
    border = (
        [(row, 0) for row in range(height)]
        + [(row, width - 1) for row in range(height)]
        + [(0, col) for col in range(width)]
        + [(height - 1, col) for col in range(width)]
    )
    for point in border:
        if point not in seen and grid[point[0]][point[1]] == background:
            seen.add(point)
            pending.append(point)
    while pending:
        row, col = pending.pop()
        for row_step, col_step in _directions(connectivity):
            next_row = row + row_step
            next_col = col + col_step
            point = (next_row, next_col)
            if not (0 <= next_row < height and 0 <= next_col < width):
                continue
            if point in seen or grid[next_row][next_col] != background:
                continue
            seen.add(point)
            pending.append(point)
    return seen


def _enclosed_background(grid: Grid, background: int, connectivity: int) -> set[Point]:
    exterior = _exterior_background(grid, background, connectivity)
    return {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == background and (row, col) not in exterior
    }


def apply_region(program: Mapping[str, Any], grid: Grid) -> Grid:
    background = int(program["background"])
    fill_color = int(program["fill_color"])
    connectivity = int(program["connectivity"])
    mode = str(program["mode"])
    enclosed = _enclosed_background(grid, background, connectivity)
    if mode == "fill_copy":
        output = deepcopy(grid)
        for row, col in enclosed:
            output[row][col] = fill_color
        return output
    if mode == "highlight":
        output = [[background for _ in values] for values in grid]
        for row, col in enclosed:
            output[row][col] = fill_color
        return output
    if mode == "solidify":
        exterior = _exterior_background(grid, background, connectivity)
        return [
            [background if (row, col) in exterior else fill_color for col in range(len(grid[0]))]
            for row in range(len(grid))
        ]
    raise ValueError("unknown enclosed region mode")


def _fits(program: Program, demos: Sequence[tuple[Grid, Grid]]) -> bool:
    try:
        return all(apply_region(program, source) == target for source, target in demos)
    except (KeyError, TypeError, ValueError):
        return False


def _modal_color(grid: Grid) -> int:
    counts = Counter(cell for row in grid for cell in row)
    highest = max(counts.values())
    return min(color for color, count in counts.items() if count == highest)


def _background_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[int, ...]:
    common = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common.intersection_update(cell for row in source for cell in row)
    candidates = {0} if 0 in common else set()
    modal_colors = {_modal_color(source) for source, _ in demos}
    if len(modal_colors) == 1:
        candidates.update(modal_colors & common)
    return tuple(sorted(candidates))


def region_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[Program, ...]:
    target_colors = sorted({cell for _, target in demos for row in target for cell in row})
    candidates: list[Program] = []
    for background in _background_candidates(demos):
        for connectivity in (4, 8):
            for mode in ("fill_copy", "highlight", "solidify"):
                for fill_color in target_colors:
                    program = {
                        "kind": "enclosed_region_fill",
                        "background": background,
                        "connectivity": connectivity,
                        "mode": mode,
                        "fill_color": fill_color,
                    }
                    if _fits(program, demos):
                        candidates.append(program)
    return tuple(candidates)
