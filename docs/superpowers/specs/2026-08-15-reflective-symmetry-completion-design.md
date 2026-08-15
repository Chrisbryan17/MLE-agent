# Reflective Symmetry Completion Design

## Goal

Add one generic ARC primitive that completes an input by reflecting its original non-background cells through one demonstrated symmetry while preserving the source cells in place.

The exhaustive training-only scan over all 1,000 ARC training tasks found exactly four compatible residual tasks under individual shape-preserving transforms:

- `496994bd`: horizontal reflection and 180-degree rotation both fit the demonstrations and agree on the hidden output; exact acceptance is safe by hidden-output consensus.
- `e729b7be`: 180-degree rotational completion; unique fitting program and exact hidden output.
- `f25ffba3`: horizontal reflective completion; unique fitting program and exact hidden output.
- `b8825c91`: vertical reflection and 180-degree rotation both fit demonstrations but produce two hidden output classes. The correct action is `AMBIGUOUS_PROGRAM`.

No currently accepted training task fits this family. There are zero wrong accepted hidden outputs when existing consensus is applied.

## Baseline and Acceptance Boundary

The immutable pre-symmetry checkpoint is same-color line connection V2.2 at candidate `df779fa892b9ce3bfddab4d03aa743a97d22d1b3`:

- 1,000 training tasks / 1,076 hidden rows.
- 96 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 1 `AMBIGUOUS_PROGRAM` row.
- 979 `GRAMMAR_EXHAUSTED` rows.
- 1,000 compact/mechanistic parity checks.
- frozen V2.1 byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.

Acceptance requires exactly:

- 99 accepted and correct rows.
- 0 incorrect attempts.
- 0 failures.
- 2 `AMBIGUOUS_PROGRAM` rows.
- 975 `GRAMMAR_EXHAUSTED` rows.
- 40 cumulative gain tasks over the original `e509650...` training baseline.
- no lost prior-correct row and no changed prior mechanism guard.

`b8825c91` must specifically transition from `GRAMMAR_EXHAUSTED` to `AMBIGUOUS_PROGRAM` with at least two symmetry-completion output classes.

## Program Schema

```python
{
    "kind": "reflective_symmetry_complete",
    "background": 0,
    "transform": "vertical" | "horizontal" | "rotate_180" | "main_diagonal" | "anti_diagonal",
}
```

Canonical transform order is exactly the order shown above.

## Execution Semantics

The input grid is copied unchanged first. Reflection claims are derived only from original non-background cells; newly written cells never become new anchors.

For every original non-background cell `(row, col, color)`:

- `vertical`: map to `(row, width - 1 - col)`.
- `horizontal`: map to `(height - 1 - row, col)`.
- `rotate_180`: map to `(height - 1 - row, width - 1 - col)`.
- `main_diagonal`: square grids only; map to `(col, row)`.
- `anti_diagonal`: square grids only; map to `(width - 1 - col, height - 1 - row)`.

The reflected cell is written only when the original target cell is background or already the same color. A reflected claim that would overwrite a different original non-background color fails. Different-color reflected claims on the same cell also fail. Same-color overlap is allowed.

Execution preserves input shape and all original cell values.

## Candidate Derivation

`symmetry_complete_programs(demos)`:

1. Require at least one demonstration.
2. Require source and target shape equality in every demonstration; otherwise return `NO_SHAPE_PRESERVING_SYMMETRY`.
3. Intersect source colors across demonstrations to obtain background candidates.
4. Enumerate backgrounds ascending and transforms in canonical order.
5. Execute each candidate on every demonstration.
6. Retain only candidates reproducing every target exactly.
7. Require at least one demonstration to change; no-op candidates are omitted.
8. Return all fitting candidates without preference.
9. If none fit, return `NO_REFLECTIVE_SYMMETRY_COMPLETION`.

Existing hidden-output equivalence and consensus logic decides acceptance or ambiguity. No transform is preferred merely because it appears earlier.

## Training-Only Discovery Evidence

Canonical family scan results:

```text
496994bd -> background 0 -> horizontal, rotate_180 -> one exact hidden output class
b8825c91 -> background 4 -> vertical, rotate_180   -> two hidden output classes -> abstain
e729b7be -> background 7 -> rotate_180             -> exact
f25ffba3 -> background 0 -> horizontal             -> exact
```

No accepted task overlaps this family.

Pinned fixture SHA-256 digests:

```text
496994bd.json  ecc40bb943911e33cdfc1e668a5bb49b22ad55a662aa37d68ba57e884897dc25
b8825c91.json  ccf892a7ba8797ab4c69b241d80dd389cde0b9c7b8c0667a8b3a273873c4d49d
e729b7be.json  d2565e3c8e6482a1a3cec2ccf604032c223ee6d6f579dfee98a72b4cbdc12c99
f25ffba3.json  98bd5da81220ac72cf0a2d8ae093ed602066e14cb28ffce6db3110d91382067c
```

## Integration

Create `research/universal_core/holonomy_v2_2/symmetry_complete.py` exposing:

```python
apply_symmetry_complete(program, grid)
symmetry_complete_programs(demos)
```

Then:

- `grid_induction.py`: dispatch `reflective_symmetry_complete` and advance `grid-v2.2-15` to `grid-v2.2-16`.
- `grid_mechanistic_runtime.py`: register generator prefix `symmetry_complete:` immediately after `line_connect`.

## TDD and Evidence Requirements

1. Pin all four exact fixtures from immutable benchmark run `30929169392`; verify digests before commit.
2. Commit execution, diagonal-shape, conflict, derivation, no-op, three exact-real-task, and one ambiguity-real-task tests before production code.
3. Confirm missing-module RED.
4. Implement isolated module and pass module-only GREEN.
5. Wire only through a fail-closed integration workflow.
6. Run all 1,000 training tasks with complete traces and parity.
7. Require exactly three new correct gains, `b8825c91` ambiguity, exact 99/2/975 statuses, zero wrong accepts, and all prior mechanism guards.
8. Independently verify the artifact and seal immutable evidence.
9. Do not rerun public ARC evaluation.
