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
    raise ValueError("bounding-box connectivity must be four or eight")


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


def _bounds(cells: Sequence[Point]) -> tuple[int, int, int, int]:
    if not cells:
        raise ValueError("bounding-box completion requires a foreground cell")
    return (
        min(row for row, _ in cells),
        max(row for row, _ in cells),
        min(col for _, col in cells),
        max(col for _, col in cells),
    )


def _groups(program: Mapping[str, Any], grid: Grid) -> tuple[Component, ...]:
    background = int(program["background"])
    scope = str(program["scope"])
    if scope == "global":
        cells = tuple(
            (row, col)
            for row, values in enumerate(grid)
            for col, value in enumerate(values)
            if value != background
        )
        if not cells:
            raise ValueError("global bounding box requires foreground")
        return (cells,)
    if scope == "components":
        components = _components(
            grid,
            background,
            int(program["connectivity"]),
        )
        if not components:
            raise ValueError("component bounding boxes require foreground")
        return components
    raise ValueError("unknown bounding-box scope")


def apply_bbox_complete(program: Mapping[str, Any], grid: Grid) -> Grid:
    background = int(program["background"])
    fill_color = int(program["fill_color"])
    mode = str(program["mode"])
    if fill_color == background:
        raise ValueError("bounding-box fill color must differ from background")
    if mode not in {"fill", "outline"}:
        raise ValueError("unknown bounding-box completion mode")

    output = deepcopy(grid)
    for cells in _groups(program, grid):
        top, bottom, left, right = _bounds(cells)
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if grid[row][col] != background:
                    continue
                on_border = row in (top, bottom) or col in (left, right)
                if mode == "fill" or on_border:
                    output[row][col] = fill_color
    return output


def _background_candidates(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[int, ...]:
    common = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common.intersection_update(cell for row in source for cell in row)
    return tuple(sorted(common))


def bbox_complete_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if any(
        len(source) != len(target) or len(source[0]) != len(target[0])
        for source, target in demos
    ):
        return (), "GRID_SHAPE_CHANGED"
    backgrounds = _background_candidates(demos)
    if not backgrounds:
        return (), "NO_BACKGROUND_CANDIDATE"
    target_colors = sorted({
        cell
        for _, target in demos
        for row in target
        for cell in row
    })
    programs: list[Program] = []
    for background in backgrounds:
        for fill_color in target_colors:
            if fill_color == background:
                continue
            for mode in ("fill", "outline"):
                programs.append({
                    "kind": "bounding_box_complete",
                    "background": background,
                    "fill_color": fill_color,
                    "mode": mode,
                    "scope": "global",
                })
                for connectivity in (4, 8):
                    programs.append({
                        "kind": "bounding_box_complete",
                        "background": background,
                        "fill_color": fill_color,
                        "mode": mode,
                        "scope": "components",
                        "connectivity": connectivity,
                    })
    if not programs:
        return (), "NO_STRUCTURAL_PROGRAM"
    return tuple(programs), None
