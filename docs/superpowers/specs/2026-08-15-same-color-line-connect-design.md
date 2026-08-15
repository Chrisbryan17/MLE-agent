# Same-Color Straight-Line Connection Design

## Goal

Add one generic ARC primitive that connects same-color source anchors along selected straight-line families without moving or recoloring existing cells.

The exhaustive training-only scan over all 1,000 ARC training tasks found exactly four compatible grammar gaps:

- `1f876c06`: diagonal connections.
- `22168020`: horizontal connections.
- `22eb0ac0`: horizontal connections.
- `ded97339`: orthogonal horizontal/vertical connections.

All fitting demonstration programs predict the exact hidden output. Demo-equivalent modes collapse to one hidden output class for every compatible task. There are zero wrong completed hidden outputs and zero overlap with already accepted tasks.

## Baseline and Acceptance Boundary

The immutable pre-line checkpoint is gravity V2.2 at candidate `3c6510a5c69ee600a7fc8d3a0a6a3e15ee9a05b1`:

- 1,000 training tasks / 1,076 hidden rows.
- 92 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 1 `AMBIGUOUS_PROGRAM` row.
- 983 `GRAMMAR_EXHAUSTED` rows.
- 1,000 compact/mechanistic parity checks.
- frozen V2.1 byte identity at `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.

Acceptance requires exactly:

- 96 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 1 `AMBIGUOUS_PROGRAM` row.
- 979 `GRAMMAR_EXHAUSTED` rows.
- 37 cumulative gain tasks over original `e509650...` baseline.
- no lost prior-correct row and no changed prior mechanism guard.

## Program Schema

```python
{
    "kind": "same_color_line_connect",
    "background": 0,
    "mode": "horizontal" | "vertical" | "orthogonal" | "diagonal" | "all",
}
```

Canonical mode order is exactly the order shown above.

## Execution Semantics

Anchors are determined once from the original source grid. Newly filled cells never become anchors and therefore cannot create cascading segments.

For every non-background color independently, selected line families are evaluated:

- horizontal: same row;
- vertical: same column;
- main diagonal: equal `row - col`;
- anti-diagonal: equal `row + col`.

For each color and line containing at least two original anchors, connect the outermost anchors by filling every cell on the straight segment with that color.

Modes select line families as follows:

```text
horizontal  -> horizontal
vertical    -> vertical
orthogonal  -> horizontal + vertical
diagonal    -> main diagonal + anti-diagonal
all         -> horizontal + vertical + both diagonals
```

All segment claims are derived from original anchors before writing output. If two different colors claim the same cell, or a segment would overwrite an existing different non-background color, execution fails. Same-color overlapping claims are allowed.

Execution preserves source shape and every existing cell value.

## Candidate Derivation

`line_connect_programs(demos)`:

1. Require at least one demonstration.
2. Require source and target shapes to match for every demonstration; otherwise return `NO_SHAPE_PRESERVING_LINE_CONNECT`.
3. Intersect source colors across demonstrations to obtain background candidates.
4. Enumerate backgrounds ascending and modes in canonical order.
5. Execute each candidate on every demonstration.
6. Retain only candidates reproducing every target exactly.
7. Require at least one demonstration to change; no-op candidates are omitted.
8. Return all fitting candidates without preference.
9. If none fit, return `NO_LINE_CONNECTION`.

Existing hidden-output equivalence and consensus logic decides acceptance or ambiguity.

## Training-Only Discovery Evidence

Canonical family scan results:

```text
1f876c06 -> background 0 -> diagonal, all
22168020 -> background 0 -> horizontal, orthogonal, all
22eb0ac0 -> background 0 -> horizontal, orthogonal, all
ded97339 -> background 0 -> orthogonal
```

For every task, all fitting candidates produce one hidden output class and that class exactly equals the hidden target.

Pinned fixture SHA-256 digests:

```text
1f876c06.json  b53a1a25685895400323e813a373f0a66fc9512f7dbbb326d52a93695fca8143
22168020.json  d067b4f83f84120300310199e3a95c65258edcc53d8b0f425288d7ddb71a962e
22eb0ac0.json  cf37cc34e7b0aa123c2806eca77a7d9916b50afea4e6e2db71d5149fe1f1af0d
ded97339.json  fd14b4ee37bb1539c26a79abed743626b37f5935794ce82cbd0b3332c207906e
```

## Integration

Create `research/universal_core/holonomy_v2_2/line_connect.py` exposing:

```python
apply_line_connect(program, grid)
line_connect_programs(demos)
```

Then:

- `grid_induction.py`: dispatch `same_color_line_connect` and advance `grid-v2.2-14` to `grid-v2.2-15`.
- `grid_mechanistic_runtime.py`: register `line_connect:` immediately after `gravity_compact`.

## TDD and Evidence Requirements

1. Pin all four exact fixtures and digest tests.
2. Commit direct horizontal, vertical, diagonal, conflict, derivation, no-op, and real-task tests before production code.
3. Confirm missing-module RED.
4. Implement isolated module and pass module-only GREEN.
5. Wire through a fail-closed integration workflow.
6. Run all 1,000 training tasks with complete traces and parity.
7. Require exactly four new gain tasks, exact 96/1/979 statuses, zero wrong accepts, and all prior mechanism guards.
8. Independently verify the artifact and seal immutable evidence.
9. Do not rerun public ARC evaluation.
