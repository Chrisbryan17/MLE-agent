from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]


def _collapse_rows(grid: Grid, scope: str) -> Grid:
    output: Grid = []
    seen: set[tuple[int, ...]] = set()
    previous: tuple[int, ...] | None = None
    for row in grid:
        key = tuple(row)
        if scope == "adjacent_runs":
            if key == previous:
                continue
            previous = key
        elif scope == "global_first":
            if key in seen:
                continue
            seen.add(key)
        else:
            raise ValueError("unknown axis collapse scope")
        output.append(list(row))
    if not output:
        raise ValueError("axis collapse removed every row")
    return output


def _collapse_columns(grid: Grid, scope: str) -> Grid:
    columns = [tuple(row[index] for row in grid) for index in range(len(grid[0]))]
    keep: list[int] = []
    seen: set[tuple[int, ...]] = set()
    previous: tuple[int, ...] | None = None
    for index, column in enumerate(columns):
        if scope == "adjacent_runs":
            if column == previous:
                continue
            previous = column
        elif scope == "global_first":
            if column in seen:
                continue
            seen.add(column)
        else:
            raise ValueError("unknown axis collapse scope")
        keep.append(index)
    if not keep:
        raise ValueError("axis collapse removed every column")
    return [[row[index] for index in keep] for row in grid]


def apply_axis_collapse(program: Mapping[str, Any], grid: Grid) -> Grid:
    scope = str(program["scope"])
    axes = str(program["axes"])
    output = [list(row) for row in grid]
    if axes == "rows":
        return _collapse_rows(output, scope)
    if axes == "columns":
        return _collapse_columns(output, scope)
    if axes == "both":
        return _collapse_columns(_collapse_rows(output, scope), scope)
    raise ValueError("unknown axis collapse axes")


def axis_collapse_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    programs: list[Program] = []
    for scope in ("adjacent_runs", "global_first"):
        for axes in ("rows", "columns", "both"):
            program = {
                "kind": "axis_duplicate_collapse",
                "scope": scope,
                "axes": axes,
            }
            if any(apply_axis_collapse(program, source) != source for source, _ in demos):
                programs.append(program)

    if not programs:
        return (), "NO_DUPLICATE_AXIS_REDUCTION"
    return tuple(programs), None
