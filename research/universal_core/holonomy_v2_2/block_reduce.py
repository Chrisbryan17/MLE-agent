from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


Grid = list[list[int]]
Program = dict[str, Any]


def _shape(grid: Grid) -> tuple[int, int]:
    if not grid or not grid[0]:
        raise ValueError("block reduction requires a nonempty grid")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("block reduction requires a rectangular grid")
    return len(grid), width


def _block_value(block: list[int], reducer: str, background: int | None) -> int:
    if reducer == "strict_mode":
        counts = Counter(block)
        highest = max(counts.values())
        modes = [color for color, count in counts.items() if count == highest]
        if len(modes) != 1:
            raise ValueError("strict mode requires a unique mode")
        return modes[0]

    if reducer == "unique_non_background":
        if background is None:
            raise ValueError("unique non-background reduction requires a background")
        colors = {color for color in block if color != background}
        if not colors:
            return background
        if len(colors) != 1:
            raise ValueError("block must contain at most one non-background color")
        return next(iter(colors))

    raise ValueError("unknown block reducer")


def apply_block_reduce(program: Mapping[str, Any], grid: Grid) -> Grid:
    height, width = _shape(grid)
    row_factor = int(program["row_factor"])
    col_factor = int(program["col_factor"])
    if row_factor < 1 or col_factor < 1:
        raise ValueError("block factors must be positive")
    if height % row_factor or width % col_factor:
        raise ValueError("grid dimensions must be divisible by block factors")

    output_height = height // row_factor
    output_width = width // col_factor
    if not 1 <= output_height <= 30 or not 1 <= output_width <= 30:
        raise ValueError("block reduction output exceeds ARC bounds")

    reducer = str(program["reducer"])
    background = int(program["background"]) if "background" in program else None
    output: Grid = []
    for out_row in range(output_height):
        row: list[int] = []
        row_start = out_row * row_factor
        for out_col in range(output_width):
            col_start = out_col * col_factor
            block = [
                grid[source_row][source_col]
                for source_row in range(row_start, row_start + row_factor)
                for source_col in range(col_start, col_start + col_factor)
            ]
            row.append(_block_value(block, reducer, background))
        output.append(row)
    return output


def _fits(program: Program, demos: Sequence[tuple[Grid, Grid]]) -> bool:
    try:
        return all(apply_block_reduce(program, source) == target for source, target in demos)
    except (KeyError, TypeError, ValueError):
        return False


def _stable_factors(demos: Sequence[tuple[Grid, Grid]]) -> tuple[int, int] | None:
    factors: tuple[int, int] | None = None
    for source, target in demos:
        source_height, source_width = _shape(source)
        target_height, target_width = _shape(target)
        if source_height % target_height or source_width % target_width:
            return None
        current = (source_height // target_height, source_width // target_width)
        if current[0] < 1 or current[1] < 1 or current == (1, 1):
            return None
        if factors is None:
            factors = current
        elif factors != current:
            return None
    return factors


def block_reduce_programs(
    demos: Sequence[tuple[Grid, Grid]],
) -> tuple[tuple[Program, ...], str | None]:
    if not demos:
        return (), "NO_DEMONSTRATION"

    factors = _stable_factors(demos)
    if factors is None:
        return (), "NO_STABLE_BLOCK_FACTORS"
    row_factor, col_factor = factors

    programs: list[Program] = []
    strict = {
        "kind": "fixed_block_reduce",
        "row_factor": row_factor,
        "col_factor": col_factor,
        "reducer": "strict_mode",
    }
    if _fits(strict, demos):
        programs.append(strict)

    common_colors = {cell for row in demos[0][0] for cell in row}
    for source, _ in demos[1:]:
        common_colors.intersection_update(cell for row in source for cell in row)
    for background in sorted(common_colors):
        program = {
            "kind": "fixed_block_reduce",
            "row_factor": row_factor,
            "col_factor": col_factor,
            "reducer": "unique_non_background",
            "background": background,
        }
        if _fits(program, demos):
            programs.append(program)

    if not programs:
        return (), "NO_SUPPORTED_BLOCK_REDUCER"
    return tuple(programs), None
