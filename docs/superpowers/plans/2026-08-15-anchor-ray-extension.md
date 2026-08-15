# Anchor-to-Border Ray Extension Implementation Plan

**Goal:** Add `anchor_ray_extend` as a generic V2.2 primitive that converts exactly `623ea044` and `d037b0a7` from grammar exhaustion to exact acceptance without changing any prior result.

## Global gates

- Training-only development on 1,000 ARC tasks / 1,076 hidden rows.
- No public ARC evaluation rerun.
- Frozen V2.1 byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- No task-ID routing or preferred fitting candidate.
- Final exact metrics: 101 correct, 101 accepted, 0 incorrect attempts, 0 failures.
- Final statuses: 101 `ACCEPTED`, 2 `AMBIGUOUS_PROGRAM`, 973 `GRAMMAR_EXHAUSTED`.
- Cumulative correct gain set: prior 40 gains plus `623ea044`, `d037b0a7`.
- Preserve ambiguity for both `60b61512` and `b8825c91`.

## Task 1 — Exact fixtures and RED contract

Pin exact payloads from immutable benchmark artifact run `30929169392`:

```text
623ea044  578ab7e47a2d67489f1103715615f719ef81e9faf773be85586803d6da44cbdd
d037b0a7  9e39a4acdb3e3bff7dd54bed5f4ab77973f4027d48beb62a9c740d8a7a0b0aee
```

Create fixture integrity and behavior tests before production code.

Direct tests cover cardinal rays, diagonal rays, combined directions, original-anchor-only behavior, cross-color claim conflict, unique demonstration derivation, shape mismatch, no-op skip, and two exact real-task mechanistic assertions.

Hosted RED accepts only missing `ray_extend` module after fixture and frozen byte checks pass.

## Task 2 — Isolated module GREEN

Create `ray_extend.py` with:

```python
apply_ray_extend(program, grid)
ray_extend_programs(demos)
```

Use original non-background anchors only. Precompute claims to the border. Reject different-color original overwrite and cross-color claim collisions. Candidate order: background ascending, then `up`, `down`, `left`, `right`, `vertical`, `horizontal`, `orthogonal`, `diagonal`, `all`. Require exact demo fit and at least one changed demo.

Run fixture plus direct tests excluding real integration assertions. Require frozen byte gate and seal module GREEN evidence.

## Task 3 — Guarded integration

Fail-closed workflow:

- `grid_induction.py`: import executor, `grid-v2.2-16` -> `grid-v2.2-17`, dispatch `anchor_ray_extend`.
- `grid_mechanistic_runtime.py`: import generator, derive after symmetry completion, append `ray_extend` after `symmetry_complete`.

Run ray, symmetry, line, gravity, block, axis, palette, quadrant, mirror, bbox, outlier, marker, mechanistic, all V2.2, frozen integration, and byte gates. Restore shared files on any failure.

## Task 4 — Strict corpus gate

Run all 1,000 tasks with 1,000 validated traces and compact/mechanistic parity.

Require:

```text
rows                  1076
correct                101
accepted               101
incorrect_attempts       0
failed                   0
ACCEPTED               101
AMBIGUOUS_PROGRAM        2
GRAMMAR_EXHAUSTED       973
```

Require exact cumulative correct gain set of 42 tasks. New tasks must select prefix `ray_extend:` with successful `anchor_ray_extend` executions. Preserve all prior mechanism selectors, `b8825c91` symmetry ambiguity, and `60b61512` bbox ambiguity.

Publish complete checksummed artifact only on full GREEN.

## Task 5 — Independent validation and sealing

Verify artifact digest, manifest, 1,000 traces, 1,000 parity checks, exact metrics/statuses/gains, two ray mechanisms, all prior selectors, both ambiguity cases, and zero wrong accepts.

Seal as `docs/evidence/arc_v2_2/TRAINING_RAY_EXTEND_0018.json`. Keep PR #40 draft and unmerged.
