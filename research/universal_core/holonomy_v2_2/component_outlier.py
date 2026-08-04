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


def _partition(
    components: Sequence[Component],
    selector: str,
) -> tuple[Component, tuple[Component, ...]]:
    if len(components) < 2:
        raise ValueError("component outlier requires at least two components")
    areas = [len(item) for item in components]
    if selector == "minimum":
        extreme = min(areas)
    elif selector == "maximum":
        extreme = max(areas)
    else:
        raise ValueError("unknown component outlier selector")
    selected = [item for item in components if len(item) == extreme]
    if len(selected) != 1:
        raise ValueError("component outlier requires one unique area extreme")
    peers = tuple(item for item in components if item != selected[0])
    if len({len(item) for item in peers}) != 1:
        raise ValueError("component peer areas must be uniform")
    return selected[0], peers


def apply_component_outlier(program: Mapping[str, Any], grid: Grid) -> Grid:
    background = int(program["background"])
    connectivity = int(program["connectivity"])
    selector = str(program["selector"])
    selected_color = int(program["selected_color"])
    other_color = int(program["other_color"])
    if selected_color == other_color:
        raise ValueError("component outlier colors must differ")
    components = _components(grid, background, connectivity)
    selected, _ = _partition(components, selector)
    output = deepcopy(grid)
    for component in components:
        color = selected_color if component == selected else other_color
        for row, col in component:
            output[row][col] = color
    return output


def _background_candidates(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[int, ...]:
    common = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common.intersection_update(cell for row in source for cell in row)
    candidates: list[int] = []
    for color in sorted(common):
        unchanged = True
        for source, target in demos:
            if len(source) != len(target) or len(source[0]) != len(target[0]):
                unchanged = False
                break
            for row_index, row in enumerate(source):
                for col_index, cell in enumerate(row):
                    if cell == color and target[row_index][col_index] != color:
                        unchanged = False
                        break
                if not unchanged:
                    break
            if not unchanged:
                break
        if unchanged:
            candidates.append(color)
    return tuple(candidates)


def _derive_program(
    demos: Sequence[tuple[Grid, Grid]],
    background: int,
    connectivity: int,
    selector: str,
) -> Program | None:
    selected_color: int | None = None
    other_color: int | None = None
    for source, target in demos:
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return None
        components = _components(source, background, connectivity)
        try:
            selected, peers = _partition(components, selector)
        except ValueError:
            return None
        covered = {point for component in components for point in component}
        for row_index, row in enumerate(source):
            for col_index, cell in enumerate(row):
                if (row_index, col_index) not in covered and target[row_index][col_index] != cell:
                    return None
        selected_colors = {target[row][col] for row, col in selected}
        peer_colors = {
            target[row][col]
            for component in peers
            for row, col in component
        }
        if len(selected_colors) != 1 or len(peer_colors) != 1:
            return None
        current_selected = next(iter(selected_colors))
        current_other = next(iter(peer_colors))
        if current_selected == current_other:
            return None
        if selected_color is None:
            selected_color = current_selected
            other_color = current_other
        elif selected_color != current_selected or other_color != current_other:
            return None
    if selected_color is None or other_color is None:
        return None
    return {
        "kind": "component_area_outlier_color",
        "background": background,
        "connectivity": connectivity,
        "selector": selector,
        "selected_color": selected_color,
        "other_color": other_color,
    }


def component_outlier_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    backgrounds = _background_candidates(demos)
    if not backgrounds:
        return (), "NO_BACKGROUND_CANDIDATE"
    programs: list[Program] = []
    for background in backgrounds:
        for connectivity in (4, 8):
            for selector in ("minimum", "maximum"):
                program = _derive_program(
                    demos,
                    background,
                    connectivity,
                    selector,
                )
                if program is not None:
                    programs.append(program)
    if not programs:
        return (), "NO_DERIVED_COMPONENT_OUTLIER_PROGRAM"
    return tuple(programs), None
