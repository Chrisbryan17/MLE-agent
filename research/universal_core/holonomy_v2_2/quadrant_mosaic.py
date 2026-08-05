from __future__ import annotations

from itertools import product
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]

_TRANSFORM_ORDER = (
    "identity",
    "rotate_90",
    "rotate_180",
    "rotate_270",
    "reflect_columns",
    "reflect_rows",
    "reflect_main_diagonal",
    "reflect_anti_diagonal",
)
_QUADRANT_FIELDS = (
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
)


def _shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0])


def _rotate_90(grid: Grid) -> Grid:
    return [list(row) for row in zip(*reversed(grid))]


def _apply_transform(name: str, grid: Grid) -> Grid:
    source = [list(row) for row in grid]
    if name == "identity":
        return source
    if name == "rotate_90":
        return _rotate_90(source)
    if name == "rotate_180":
        return [list(reversed(row)) for row in reversed(source)]
    if name == "rotate_270":
        return _rotate_90(_rotate_90(_rotate_90(source)))
    if name == "reflect_columns":
        return [list(reversed(row)) for row in source]
    if name == "reflect_rows":
        return [list(row) for row in reversed(source)]
    if name == "reflect_main_diagonal":
        return [list(row) for row in zip(*source)]
    if name == "reflect_anti_diagonal":
        transposed = [list(row) for row in zip(*source)]
        return [list(reversed(row)) for row in reversed(transposed)]
    raise ValueError("unknown quadrant mosaic transform")


def _split_quadrants(target: Grid, height: int, width: int) -> tuple[Grid, Grid, Grid, Grid]:
    return (
        [row[:width] for row in target[:height]],
        [row[width:] for row in target[:height]],
        [row[:width] for row in target[height:]],
        [row[width:] for row in target[height:]],
    )


def apply_quadrant_mosaic(program: Mapping[str, Any], grid: Grid) -> Grid:
    height, width = _shape(grid)
    if height * 2 > 30 or width * 2 > 30:
        raise ValueError("quadrant mosaic exceeds ARC bounds")

    quadrants = tuple(
        _apply_transform(str(program[field]), grid)
        for field in _QUADRANT_FIELDS
    )
    if any(_shape(item) != (height, width) for item in quadrants):
        raise ValueError("quadrant transform must preserve source shape")

    top_left, top_right, bottom_left, bottom_right = quadrants
    return (
        [top_left[row] + top_right[row] for row in range(height)]
        + [bottom_left[row] + bottom_right[row] for row in range(height)]
    )


def quadrant_mosaic_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    supported: list[set[str]] = [set(_TRANSFORM_ORDER) for _ in _QUADRANT_FIELDS]
    for source, target in demos:
        height, width = _shape(source)
        if _shape(target) != (height * 2, width * 2):
            return (), "OUTPUT_NOT_DOUBLE_SOURCE_SHAPE"
        quadrants = _split_quadrants(target, height, width)
        for index, quadrant in enumerate(quadrants):
            matches = {
                name
                for name in _TRANSFORM_ORDER
                if _shape(_apply_transform(name, source)) == (height, width)
                and _apply_transform(name, source) == quadrant
            }
            supported[index].intersection_update(matches)

    if any(not names for names in supported):
        return (), "NO_SUPPORTED_QUADRANT_TRANSFORM"
    if set.intersection(*supported):
        return (), "NO_DISTINCT_QUADRANT_ROLES"

    ordered = [
        tuple(name for name in _TRANSFORM_ORDER if name in names)
        for names in supported
    ]
    programs = tuple(
        {
            "kind": "dihedral_quadrant_mosaic",
            **{
                field: transform
                for field, transform in zip(_QUADRANT_FIELDS, transforms)
            },
        }
        for transforms in product(*ordered)
    )
    return programs, None
