from __future__ import annotations

from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]


def apply_mirror_concat(program: Mapping[str, Any], grid: Grid) -> Grid:
    axis = str(program["axis"])
    order = str(program["order"])
    if order not in {"source_first", "reflection_first"}:
        raise ValueError("unknown mirror concatenation order")

    if axis == "rows":
        if len(grid) * 2 > 30:
            raise ValueError("row mirror concatenation exceeds ARC bounds")
        source = [list(row) for row in grid]
        reflected = [list(row) for row in reversed(grid)]
        return source + reflected if order == "source_first" else reflected + source

    if axis == "columns":
        if len(grid[0]) * 2 > 30:
            raise ValueError("column mirror concatenation exceeds ARC bounds")
        output: Grid = []
        for row in grid:
            source = list(row)
            reflected = list(reversed(row))
            output.append(
                source + reflected
                if order == "source_first"
                else reflected + source
            )
        return output

    raise ValueError("unknown mirror concatenation axis")


def mirror_concat_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"
    return (
        {"kind": "mirror_concatenate", "axis": "rows", "order": "source_first"},
        {"kind": "mirror_concatenate", "axis": "rows", "order": "reflection_first"},
        {"kind": "mirror_concatenate", "axis": "columns", "order": "source_first"},
        {"kind": "mirror_concatenate", "axis": "columns", "order": "reflection_first"},
    ), None
