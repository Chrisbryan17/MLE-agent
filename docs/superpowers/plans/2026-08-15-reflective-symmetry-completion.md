# Reflective Symmetry Completion Implementation Plan

**Goal:** Add `reflective_symmetry_complete` as a generic V2.2 primitive that converts three exact training gaps to acceptance and one underdetermined training gap to explicit ambiguity without changing any prior result.

## Global gates

- Training-only development on 1,000 ARC tasks / 1,076 hidden rows.
- No public ARC evaluation rerun.
- Frozen V2.1 byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- No task-ID routing or transform preference.
- Final exact metrics: 99 correct, 99 accepted, 0 incorrect attempts, 0 failures.
- Final statuses: 99 `ACCEPTED`, 2 `AMBIGUOUS_PROGRAM`, 975 `GRAMMAR_EXHAUSTED`.
- Cumulative correct gain set: prior 37 gains plus `496994bd`, `e729b7be`, `f25ffba3`.
- `b8825c91` must transition to ambiguity, not acceptance.

## Task 1 — Exact fixtures and RED contract

Pin from immutable benchmark artifact run `30929169392`:

```text
496994bd  ecc40bb943911e33cdfc1e668a5bb49b22ad55a662aa37d68ba57e884897dc25
b8825c91  ccf892a7ba8797ab4c69b241d80dd389cde0b9c7b8c0667a8b3a273873c4d49d
e729b7be  d2565e3c8e6482a1a3cec2ccf604032c223ee6d6f579dfee98a72b4cbdc12c99
f25ffba3  98bd5da81220ac72cf0a2d8ae093ed602066e14cb28ffce6db3110d91382067c
```

Create fixture integrity and behavioral tests before production code.

Direct tests cover vertical, horizontal, 180-degree, diagonal completion, original-anchor-only behavior, cross-color conflict, non-square diagonal rejection, exact derivation, shape mismatch skip, no-op skip, three exact real tasks, and `b8825c91` hidden disagreement ambiguity.

Hosted RED accepts only missing `symmetry_complete` module after fixture and frozen-byte gates pass.

## Task 2 — Isolated module GREEN

Create `symmetry_complete.py` with:

```python
apply_symmetry_complete(program, grid)
symmetry_complete_programs(demos)
```

Use original source anchors only. Precompute reflection claims. Reject different-color collisions/overwrites. Diagonal transforms require square grids. Candidate order is background ascending then transform order `vertical`, `horizontal`, `rotate_180`, `main_diagonal`, `anti_diagonal`. Require exact demo fit and at least one changed demo.

Run fixture plus direct tests excluding real integration assertions. Require frozen byte gate and seal module GREEN evidence.

## Task 3 — Guarded integration

Fail-closed workflow:

- `grid_induction.py`: import executor, `grid-v2.2-15` -> `grid-v2.2-16`, dispatch `reflective_symmetry_complete`.
- `grid_mechanistic_runtime.py`: import generator, derive after line connection, append `symmetry_complete` after `line_connect`.

Run symmetry, line, gravity, block, axis, palette, quadrant, mirror, bbox, outlier, marker, mechanistic, all V2.2, frozen integration, and byte gates. Restore shared files on any failure.

## Task 4 — Strict corpus gate

Run all 1,000 tasks with 1,000 validated traces and compact/mechanistic parity.

Require:

```text
rows                  1076
correct                 99
accepted                99
incorrect_attempts       0
failed                   0
ACCEPTED                99
AMBIGUOUS_PROGRAM        2
GRAMMAR_EXHAUSTED       975
```

Require exact cumulative correct gain set of 40 tasks. New accepted mechanisms use prefix `symmetry_complete:` for `496994bd`, `e729b7be`, `f25ffba3`. Require `b8825c91` terminal ambiguity with at least two symmetry-completion equivalence classes. Preserve all prior mechanism guards and `60b61512` bbox ambiguity.

Publish complete checksummed artifact only on full GREEN.

## Task 5 — Independent validation and sealing

Verify artifact digest, all manifest entries, 1,000 traces, parity, exact metrics/statuses/gains, three accepted symmetry traces, both ambiguity cases, all prior guards, and zero wrong accepts.

Seal as `docs/evidence/arc_v2_2/TRAINING_SYMMETRY_COMPLETE_0017.json`. Keep PR #40 draft and unmerged.
