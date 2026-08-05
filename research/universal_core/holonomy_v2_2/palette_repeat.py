from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]


def _factor(program: Mapping[str, Any], grid: Grid) -> int:
    colors = {cell for row in grid for cell in row}
    statistic = str(program["statistic"])
    if statistic == "distinct_all":
        return len(colors)
    if statistic == "distinct_non_background":
        return len(colors - {int(program["background"])})
    raise ValueError("unknown palette cardinality statistic")


def _scale(grid: Grid, factor: int) -> Grid:
    return [
        [cell for cell in row for _ in range(factor)]
        for row in grid
        for _ in range(factor)
    ]


def _tile(grid: Grid, factor: int) -> Grid:
    return [
        list(row) * factor
        for _ in range(factor)
        for row in grid
    ]


def apply_palette_repeat(program: Mapping[str, Any], grid: Grid) -> Grid:
    factor = _factor(program, grid)
    if factor < 1:
        raise ValueError("palette repeat factor must be positive")
    if len(grid) * factor > 30 or len(grid[0]) * factor > 30:
        raise ValueError("palette repeat exceeds ARC bounds")

    operation = str(program["operation"])
    if operation == "scale":
        return _scale(grid, factor)
    if operation == "tile":
        return _tile(grid, factor)
    raise ValueError("unknown palette repeat operation")


def _candidate_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[Program, ...]:
    programs: list[Program] = []
    for operation in ("scale", "tile"):
        programs.append({
            "kind": "palette_cardinality_repeat",
            "operation": operation,
            "statistic": "distinct_all",
        })

    common_backgrounds = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)
    for operation in ("scale", "tile"):
        for background in sorted(common_backgrounds):
            programs.append({
                "kind": "palette_cardinality_repeat",
                "operation": operation,
                "statistic": "distinct_non_background",
                "background": background,
            })
    return tuple(programs)


def palette_repeat_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    fitting: list[Program] = []
    constant_fit = False
    for program in _candidate_programs(demos):
        factors: list[int] = []
        exact = True
        for source, target in demos:
            try:
                factors.append(_factor(program, source))
                output = apply_palette_repeat(program, source)
            except (KeyError, TypeError, ValueError):
                exact = False
                break
            if output != target:
                exact = False
                break
        if not exact:
            continue
        if len(set(factors)) < 2:
            constant_fit = True
            continue
        fitting.append(program)

    if fitting:
        return tuple(fitting), None
    if constant_fit:
        return (), "NO_FACTOR_VARIATION"
    return (), "NO_SUPPORTED_PALETTE_REPEAT"
