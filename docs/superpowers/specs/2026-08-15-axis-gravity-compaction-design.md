# Axis Gravity Compaction Design

## Goal

Add one generic ARC grid primitive that compacts all non-background cells within independent rows or columns toward a selected edge while preserving lane order, color identity, grid shape, and per-lane non-background counts.

The training-only discovery scan found exactly two compatible grammar gaps across all 1,000 ARC training tasks:

- `1e0a9b12`: compact each column downward through background `0`.
- `3906de3d`: compact each column upward through background `0`.

No other training task fits any candidate in this family. Both compatible tasks have exactly one fitting candidate, exact hidden outputs, zero wrong completed hidden outputs, and zero hidden-output ambiguity.

## Baseline and Acceptance Boundary

The immutable pre-gravity checkpoint is fixed-block V2.2 at candidate commit `c3c4efaef66e2ff6b8f83c5381acdec13cb31f5e`:

- 1,000 ARC training tasks / 1,076 hidden rows.
- 90 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 1 `AMBIGUOUS_PROGRAM` row.
- 985 `GRAMMAR_EXHAUSTED` rows.
- 1,000 compact/mechanistic parity checks.
- frozen V2.1 byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.

The gravity primitive is accepted only if the strict corpus becomes exactly:

- 92 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 1 `AMBIGUOUS_PROGRAM` row.
- 983 `GRAMMAR_EXHAUSTED` rows.
- 33 cumulative gain tasks over the original `e509650...` training baseline.
- no lost prior-correct row and no changed prior mechanism guard.

## Program Schema

```python
{
    "kind": "axis_gravity_compact",
    "background": 0,
    "direction": "up" | "down" | "left" | "right",
}
```

No task IDs, coordinates, task-specific colors, or corpus-specific routing are part of the program.

## Execution Semantics

### Vertical directions

For every column independently:

1. Read cells from top to bottom.
2. Remove cells equal to `background`.
3. Preserve the exact order of the remaining cells.
4. For `up`, write the sequence from the top and fill the remainder with `background`.
5. For `down`, fill the prefix with `background` and write the sequence ending at the bottom.

### Horizontal directions

For every row independently, apply the same process from left to right:

- `left` writes the preserved sequence at the left edge.
- `right` writes the preserved sequence at the right edge.

### Invariants

Execution must preserve:

- input height and width;
- every lane's multiset of cell colors;
- every lane's relative order of non-background cells;
- the total count of each color;
- rectangularity and ARC cell values.

An unknown direction is an error.

## Candidate Derivation

`gravity_compact_programs(demos)` enumerates only demonstration-supported candidates:

1. Require at least one demonstration.
2. Require every target to have the same shape as its source; otherwise return `NO_SHAPE_PRESERVING_GRAVITY`.
3. Compute colors common to every demonstration source as background candidates.
4. For each common background in sorted order and each direction in canonical order `up`, `down`, `left`, `right`, execute the candidate on every demonstration.
5. Retain a candidate only when it reproduces every demonstration target exactly.
6. Require the candidate to change at least one demonstration source; identity-equivalent candidates are not emitted.
7. If none remain, return `NO_GRAVITY_COMPACTION`.
8. Return all retained candidates without preference. Existing hidden-output equivalence/consensus logic decides acceptance or ambiguity.

This design deliberately does not infer one direction from heuristic geometry or choose among multiple fitting candidates.

## Training-Only Discovery Evidence

An exhaustive prototype enumerated the full candidate family over all 1,000 training tasks:

```text
1e0a9b12 -> background=0, direction=down -> exact hidden output
3906de3d -> background=0, direction=up   -> exact hidden output
```

Family-wide scan result:

- compatible tasks: 2;
- fitting programs: 2 total;
- compatible tasks with multiple hidden output classes: 0;
- wrong completed hidden outputs: 0;
- compatible already-accepted tasks: 0.

The two pinned fixture SHA-256 digests from the immutable benchmark ZIP are:

```text
1e0a9b12.json  6a71dbedc8403bd28fa76bd8b472597a8ecaab3af31151a2a3b72baeadd5e617
3906de3d.json  b4c20d433380e00840a75c6976ad0d0fabd80e052ab77b47422d64b1cae5f6dc
```

## Integration

Create `research/universal_core/holonomy_v2_2/gravity_compact.py` exposing:

```python
apply_gravity_compact(program, grid)
gravity_compact_programs(demos)
```

Then integrate through:

- `grid_induction.py`: import executor, dispatch `axis_gravity_compact`, advance `grid-v2.2-13` to `grid-v2.2-14`.
- `grid_mechanistic_runtime.py`: register generator prefix `gravity_compact:` after `block_reduce`.

The generator remains structurally independent from fixed-block reduction, axis duplicate collapse, and all earlier primitives.

## TDD and Evidence Requirements

1. Pin exact fixtures and byte digests.
2. Commit direct execution, derivation, exact real-task, and no-op-boundary tests before production code.
3. Confirm RED from missing `gravity_compact` module.
4. Implement the isolated module and pass module-only GREEN.
5. Wire shared runtime only through a fail-closed workflow that restores both shared files on any regression.
6. Run the complete 1,000-task training corpus with 1,000 traces and parity verification.
7. Require exactly two new gain tasks and the 92/1/983 status boundary.
8. Verify the published artifact independently and seal immutable evidence under `docs/evidence/arc_v2_2/`.
9. Do not rerun the public ARC evaluation split.
