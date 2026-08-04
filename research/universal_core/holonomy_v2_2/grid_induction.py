from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from research.universal_core.holonomy_v2.blind_adapter import run_public_task_v2

from .panel_combine import apply_panel, panel_candidates
from .region_fill import apply_region, region_candidates
from .component_select import apply_component_select, component_select_candidates


Grid = list[list[int]]
Program = dict[str, Any]
Point = tuple[int, int]
_VERSION = "grid-v2.2-5"


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value[key]
    return getattr(value, key)


def _grid(value: Any) -> Grid:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 30:
        raise ValueError("grid height must be between 1 and 30")
    width: int | None = None
    copied: Grid = []
    for row in value:
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= 30:
            raise ValueError("grid width must be between 1 and 30")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("grid must be rectangular")
        out_row: list[int] = []
        for cell in row:
            if type(cell) is not int or not 0 <= cell <= 9:
                raise ValueError("grid cells must be integers from 0 through 9")
            out_row.append(cell)
        copied.append(out_row)
    return copied


def _demo_pair(item: Any) -> tuple[Grid, Grid]:
    return _grid(_get(item, "input")), _grid(_get(item, "output"))


def _is_grid_task(task: Any) -> bool:
    try:
        demos = tuple(_get(task, "demonstrations"))
        if not demos:
            return False
        for item in demos:
            _demo_pair(item)
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _rotate(grid: Grid, turns: int) -> Grid:
    current = deepcopy(grid)
    for _ in range(turns % 4):
        current = [list(row) for row in zip(*reversed(current))]
    return current


def _reflect(grid: Grid, axis: str) -> Grid:
    if axis == "columns":
        return [list(reversed(row)) for row in grid]
    if axis == "rows":
        return [list(row) for row in reversed(grid)]
    if axis == "main":
        return [list(row) for row in zip(*grid)]
    if axis == "anti":
        return _rotate([list(row) for row in zip(*grid)], 2)
    raise ValueError("unknown reflection axis")


def _scale(grid: Grid, row_factor: int, col_factor: int) -> Grid:
    if row_factor < 1 or col_factor < 1:
        raise ValueError("scale factors must be positive")
    output: Grid = []
    for row in grid:
        expanded = [cell for cell in row for _ in range(col_factor)]
        for _ in range(row_factor):
            output.append(list(expanded))
    if len(output) > 30 or len(output[0]) > 30:
        raise ValueError("scaled grid exceeds ARC bounds")
    return output


def _tile(grid: Grid, row_repeats: int, col_repeats: int) -> Grid:
    if row_repeats < 1 or col_repeats < 1:
        raise ValueError("tile repeats must be positive")
    output = [row * col_repeats for _ in range(row_repeats) for row in grid]
    if len(output) > 30 or len(output[0]) > 30:
        raise ValueError("tiled grid exceeds ARC bounds")
    return output


def _crop(grid: Grid, background: int) -> Grid:
    cells = [
        (row_index, col_index)
        for row_index, row in enumerate(grid)
        for col_index, cell in enumerate(row)
        if cell != background
    ]
    if not cells:
        raise ValueError("crop requires a foreground cell")
    top = min(item[0] for item in cells)
    bottom = max(item[0] for item in cells)
    left = min(item[1] for item in cells)
    right = max(item[1] for item in cells)
    return [row[left : right + 1] for row in grid[top : bottom + 1]]


def _components(grid: Grid, background: int) -> tuple[tuple[Point, ...], ...]:
    height = len(grid)
    width = len(grid[0])
    seen: set[Point] = set()
    found: list[tuple[Point, ...]] = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] == background:
                continue
            color = grid[row][col]
            pending = [(row, col)]
            seen.add((row, col))
            cells: list[Point] = []
            while pending:
                current = pending.pop()
                cells.append(current)
                for row_step, col_step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
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


def _rank_key(components: Sequence[Sequence[Point]], cells: Sequence[Point], mode: str) -> str:
    sizes = sorted({len(item) for item in components})
    size = len(cells)
    if mode == "rank":
        return str(sizes.index(size))
    if mode == "extreme":
        if len(sizes) == 1:
            return "only"
        if size == sizes[0]:
            return "min"
        if size == sizes[-1]:
            return "max"
        return "mid"
    raise ValueError("unknown component rank mode")


def _apply_component_rank(program: Program, grid: Grid) -> Grid:
    background = int(program["background"])
    mode = str(program["mode"])
    mapping = {str(key): int(value) for key, value in program["mapping"].items()}
    components = _components(grid, background)
    output = deepcopy(grid)
    for cells in components:
        key = _rank_key(components, cells, mode)
        if key not in mapping:
            raise KeyError("unmapped component rank")
        for row, col in cells:
            output[row][col] = mapping[key]
    return output


def _apply(program: Program, value: Any) -> Grid:
    grid = _grid(value)
    kind = program["kind"]
    if kind == "identity":
        return grid
    if kind == "rotate":
        return _rotate(grid, int(program["turns"]))
    if kind == "reflect":
        return _reflect(grid, str(program["axis"]))
    if kind == "scale":
        return _scale(grid, int(program["rows"]), int(program["cols"]))
    if kind == "tile":
        return _tile(grid, int(program["rows"]), int(program["cols"]))
    if kind == "crop":
        return _crop(grid, int(program["background"]))
    if kind == "component_rank_color":
        return _apply_component_rank(program, grid)
    if kind == "panel_boolean_combine":
        return apply_panel(program, grid)
    if kind == "enclosed_region_fill":
        return apply_region(program, grid)
    if kind == "component_area_select":
        return apply_component_select(program, grid)
    if kind == "color_map":
        mapping = {int(key): int(item) for key, item in program["mapping"].items()}
        if any(cell not in mapping for row in grid for cell in row):
            raise KeyError("unmapped grid cell")
        return [[mapping[cell] for cell in row] for row in grid]
    raise ValueError("unknown grid program")


def _fits(program: Program, demos: Sequence[tuple[Grid, Grid]]) -> bool:
    try:
        return all(_apply(program, source) == target for source, target in demos)
    except (KeyError, TypeError, ValueError):
        return False


def _color_map(demos: Sequence[tuple[Grid, Grid]]) -> Program | None:
    mapping: dict[int, int] = {}
    for source, target in demos:
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return None
        for source_row, target_row in zip(source, target):
            for before, after in zip(source_row, target_row):
                if before in mapping and mapping[before] != after:
                    return None
                mapping[before] = after
    return {"kind": "color_map", "mapping": {str(key): mapping[key] for key in sorted(mapping)}}


def _component_rank_program(
    demos: Sequence[tuple[Grid, Grid]],
    background: int,
    mode: str,
) -> Program | None:
    mapping: dict[str, int] = {}
    for source, target in demos:
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return None
        components = _components(source, background)
        if not components:
            return None
        covered = {point for cells in components for point in cells}
        for cells in components:
            target_colors = {target[row][col] for row, col in cells}
            if len(target_colors) != 1:
                return None
            key = _rank_key(components, cells, mode)
            target_color = next(iter(target_colors))
            if key in mapping and mapping[key] != target_color:
                return None
            mapping[key] = target_color
        for row, source_row in enumerate(source):
            for col, source_color in enumerate(source_row):
                if (row, col) not in covered and target[row][col] != source_color:
                    return None
    return {
        "kind": "component_rank_color",
        "background": background,
        "mode": mode,
        "mapping": {key: mapping[key] for key in sorted(mapping)},
    }


def _dimension_program(
    demos: Sequence[tuple[Grid, Grid]],
    kind: str,
) -> Program | None:
    first_source, first_target = demos[0]
    if len(first_target) % len(first_source) or len(first_target[0]) % len(first_source[0]):
        return None
    rows = len(first_target) // len(first_source)
    cols = len(first_target[0]) // len(first_source[0])
    if rows < 1 or cols < 1:
        return None
    data = {"kind": kind, "rows": rows, "cols": cols}
    return data if _fits(data, demos) else None


def _candidate_programs(demos: Sequence[tuple[Grid, Grid]]) -> tuple[Program, ...]:
    candidates: list[Program] = [
        {"kind": "identity"},
        {"kind": "rotate", "turns": 1},
        {"kind": "rotate", "turns": 2},
        {"kind": "rotate", "turns": 3},
        {"kind": "reflect", "axis": "columns"},
        {"kind": "reflect", "axis": "rows"},
        {"kind": "reflect", "axis": "main"},
        {"kind": "reflect", "axis": "anti"},
    ]
    mapped = _color_map(demos)
    if mapped is not None:
        candidates.append(mapped)
    for kind in ("scale", "tile"):
        data = _dimension_program(demos, kind)
        if data is not None:
            candidates.append(data)
    backgrounds = sorted({cell for source, _ in demos for row in source for cell in row})
    candidates.extend({"kind": "crop", "background": item} for item in backgrounds)
    common_backgrounds = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)
    for background in sorted(common_backgrounds):
        for mode in ("rank", "extreme"):
            data = _component_rank_program(demos, background, mode)
            if data is not None:
                candidates.append(data)

    candidates.extend(panel_candidates(demos))
    candidates.extend(region_candidates(demos))
    candidates.extend(component_select_candidates(demos))

    by_digest: dict[str, Program] = {}
    for candidate in candidates:
        if _fits(candidate, demos):
            by_digest.setdefault(_digest(candidate), candidate)
    return tuple(by_digest[key] for key in sorted(by_digest))


def _evidence(candidates: Sequence[Program], batch_count: int) -> dict[str, Any]:
    return {
        "version": _VERSION,
        "candidate_count": len(candidates),
        "prediction_batch_count": batch_count,
        "candidate_kinds": sorted({str(item["kind"]) for item in candidates}),
    }


def _abstain(task_id: str, hidden_count: int, status: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "tier": "V2.2-GRID",
        "program_digest": None,
        "freeze_digest": None,
        "prediction_digest": None,
        "evidence": dict(evidence),
        "predictions": [
            {"status": status, "prediction": None}
            for _ in range(hidden_count)
        ],
    }

def run_public_task_v2_2(
    task: Any,
    engine: Any,
    *,
    mechanistic: bool = False,
) -> dict[str, Any]:
    if not _is_grid_task(task):
        result = run_public_task_v2(task, engine)
        if not mechanistic:
            return result
        from .grid_mechanistic_runtime import attach_delegate_trace

        return attach_delegate_trace(task, result)

    from .grid_mechanistic_runtime import run_grid_task

    return run_grid_task(task, mechanistic=mechanistic)
