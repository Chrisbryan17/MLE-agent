# Anchor-to-Border Ray Extension Design

## Goal

Add one generic ARC primitive that extends every original non-background anchor toward selected grid borders along canonical straight directions, preserving original cells and rejecting color conflicts.

An exhaustive training-only scan over all 1,000 ARC training tasks found exactly two compatible tasks:

- `623ea044`: background `0`, diagonal rays.
- `d037b0a7`: background `0`, downward rays.

Each task has exactly one fitting program/output class, the hidden prediction is exact, there are zero wrong completed hidden outputs, and no currently accepted task fits this family.

## Baseline and Acceptance Boundary

The immutable pre-ray checkpoint is reflective symmetry V2.2 at candidate `18573507deb284e42d573085909bbf76be5abcb8`:

- 1,000 training tasks / 1,076 hidden rows.
- 99 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 2 `AMBIGUOUS_PROGRAM` rows.
- 975 `GRAMMAR_EXHAUSTED` rows.
- 1,000 compact/mechanistic parity checks.
- frozen V2.1 byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.

Acceptance requires exactly:

- 101 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 2 `AMBIGUOUS_PROGRAM` rows.
- 973 `GRAMMAR_EXHAUSTED` rows.
- 42 cumulative correct gain tasks over original `e509650...`.
- no lost prior-correct row, no changed prior mechanism guard, and both existing ambiguity cases preserved.

## Program Schema

```python
{
    "kind": "anchor_ray_extend",
    "background": 0,
    "mode": "up" | "down" | "left" | "right" | "vertical" | "horizontal" | "orthogonal" | "diagonal" | "all",
}
```

Canonical mode order is exactly the order shown above.

## Execution Semantics

Anchors are all original source cells whose color differs from `background`. Newly written cells never become anchors.

Mode directions:

```text
up          -> N
down        -> S
left        -> W
right       -> E
vertical    -> N + S
horizontal  -> W + E
orthogonal  -> N + S + W + E
diagonal    -> NW + NE + SW + SE
all         -> all eight directions
```

For each original anchor and each selected direction, claim every in-bounds cell from the adjacent position through the border with the anchor color.

A claim fails if it would overwrite an original different non-background color or if two different anchor colors claim the same cell. Same-color overlaps are allowed. Claims are computed from original anchors only and applied after validation.

Execution preserves grid shape and every original cell value.

## Candidate Derivation

`ray_extend_programs(demos)`:

1. Require at least one demonstration.
2. Require source and target shape equality in every demo; otherwise return `NO_SHAPE_PRESERVING_RAY_EXTENSION`.
3. Intersect source colors across demos to obtain background candidates.
4. Enumerate backgrounds ascending and modes in canonical order.
5. Execute each candidate on every demonstration.
6. Retain only exact demo fits.
7. Require at least one demo source to change; no-op candidates are omitted.
8. Return all fitting candidates without preference.
9. If none fit, return `NO_RAY_EXTENSION`.

Existing hidden-output consensus decides acceptance or ambiguity.

## Training-Only Discovery Evidence

Full 1,000-task family scan:

```text
623ea044 -> background=0, mode=diagonal -> exact hidden output
d037b0a7 -> background=0, mode=down     -> exact hidden output
```

No other task fits. No current acceptance overlaps.

Pinned fixture SHA-256 digests:

```text
623ea044.json  578ab7e47a2d67489f1103715615f719ef81e9faf773be85586803d6da44cbdd
d037b0a7.json  9e39a4acdb3e3bff7dd54bed5f4ab77973f4027d48beb62a9c740d8a7a0b0aee
```

## Integration

Create `research/universal_core/holonomy_v2_2/ray_extend.py` exposing:

```python
apply_ray_extend(program, grid)
ray_extend_programs(demos)
```

Then:

- `grid_induction.py`: dispatch `anchor_ray_extend` and advance `grid-v2.2-16` to `grid-v2.2-17`.
- `grid_mechanistic_runtime.py`: register generator prefix `ray_extend:` immediately after `symmetry_complete`.

## TDD and Evidence Requirements

1. Pin both exact fixtures from immutable benchmark run `30929169392` and verify digests before commit.
2. Commit cardinal/diagonal/multi-direction execution, original-anchor-only, collision, derivation, shape/no-op, and two real-task tests before production code.
3. Confirm missing-module RED.
4. Implement isolated module and pass module-only GREEN.
5. Wire via fail-closed integration workflow.
6. Run all 1,000 training tasks with complete traces and parity.
7. Require exactly two new accepted gains, exact 101/2/973 statuses, zero wrong accepts, and all prior mechanism/ambiguity guards.
8. Independently verify the artifact and seal immutable evidence.
9. Do not rerun public ARC evaluation.
