from __future__ import annotations

from collections import Counter
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
    raise ValueError("component connectivity must be four or eight")


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


def _unique_extreme(components: Sequence[Component], selector: str) -> Component:
    if not components:
        raise ValueError("component selection requires a foreground component")
    areas = [len(item) for item in components]
    if selector == "minimum":
        extreme = min(areas)
    elif selector == "maximum":
        extreme = max(areas)
    else:
        raise ValueError("unknown component area selector")
    selected = [item for item in components if len(item) == extreme]
    if len(selected) != 1:
        raise ValueError("component area selector requires a unique extreme")
    return selected[0]


def _crop_component(grid: Grid, cells: Component, background: int) -> Grid:
    top = min(row for row, _ in cells)
    bottom = max(row for row, _ in cells)
    left = min(col for _, col in cells)
    right = max(col for _, col in cells)
    selected = set(cells)
    return [
        [
            grid[row][col] if (row, col) in selected else background
            for col in range(left, right + 1)
        ]
        for row in range(top, bottom + 1)
    ]


def apply_component_select(program: Mapping[str, Any], grid: Grid) -> Grid:
    background = int(program["background"])
    connectivity = int(program["connectivity"])
    selector = str(program["selector"])
    components = _components(grid, background, connectivity)
    selected = _unique_extreme(components, selector)
    return _crop_component(grid, selected, background)


def _fits(program: Program, demos: Sequence[tuple[Grid, Grid]]) -> bool:
    try:
        return all(apply_component_select(program, source) == target for source, target in demos)
    except (KeyError, TypeError, ValueError):
        return False


def _mode(values: Sequence[int]) -> int:
    counts = Counter(values)
    highest = max(counts.values())
    return min(color for color, count in counts.items() if count == highest)


def _modal_color(grid: Grid) -> int:
    return _mode([cell for row in grid for cell in row])


def _corner_mode(grid: Grid) -> int:
    return _mode([grid[0][0], grid[0][-1], grid[-1][0], grid[-1][-1]])


def _background_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[int, ...]:
    common = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common.intersection_update(cell for row in source for cell in row)
    if 0 in common:
        return (0,)
    candidates: set[int] = set()
    modal_colors = {_modal_color(source) for source, _ in demos}
    if len(modal_colors) == 1:
        candidates.update(modal_colors & common)
    corner_colors = {_corner_mode(source) for source, _ in demos}
    if len(corner_colors) == 1:
        candidates.update(corner_colors & common)
    return tuple(sorted(candidates))


def component_select_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    backgrounds = _background_candidates(demos)
    if not backgrounds:
        return (), "NO_BACKGROUND_CANDIDATE"
    programs: list[Program] = []
    for background in backgrounds:
        for connectivity in (4, 8):
            for selector in ("minimum", "maximum"):
                programs.append({
                    "kind": "component_area_select",
                    "background": background,
                    "connectivity": connectivity,
                    "selector": selector,
                })
    if not programs:
        return (), "NO_STRUCTURAL_PROGRAM"
    return tuple(programs), None


def component_select_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[Program, ...]:
    programs, _ = component_select_programs(demos)
    return tuple(program for program in programs if _fits(program, demos))
