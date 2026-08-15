# Axis Gravity Compaction Implementation Plan

**Goal:** Add `axis_gravity_compact` as a generic V2.2 training-only primitive that converts exactly `1e0a9b12` and `3906de3d` from grammar exhaustion to exact acceptance without changing any prior result.

**Architecture:** A standalone `gravity_compact.py` executor compacts non-background cells independently within rows or columns while preserving order. Candidate derivation enumerates common demonstrated backgrounds and four canonical directions, retains only exact non-no-op demonstration fits, and delegates hidden disagreement to the existing consensus machinery.

## Global gates

- Develop only against the 1,000 ARC training tasks.
- Never rerun the 120-task public ARC evaluation split during this cycle.
- Never modify `research/universal_core/holonomy_v2`; byte gate against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- No task-ID routing or preferred candidate heuristic.
- Preserve all prior selected mechanism prefixes.
- Preserve `60b61512` as `AMBIGUOUS_PROGRAM` with at least two bbox output classes.
- Expected final training metrics: 1,076 rows, 92 correct, 92 accepted, 0 incorrect attempts, 0 failures.
- Expected final statuses: 92 `ACCEPTED`, 1 `AMBIGUOUS_PROGRAM`, 983 `GRAMMAR_EXHAUSTED`.

## Task 1 — Pin fixtures and RED contract

Create:

- `research/universal_core/holonomy_v2_2/tests/fixtures/gravity_compact/1e0a9b12.json`
- `research/universal_core/holonomy_v2_2/tests/fixtures/gravity_compact/3906de3d.json`
- `research/universal_core/holonomy_v2_2/tests/test_gravity_compact_fixtures.py`
- `research/universal_core/holonomy_v2_2/tests/test_gravity_compact.py`
- `.github/workflows/arc-gravity-compact-red.yml`

Fixture SHA-256 values must be exactly:

```text
1e0a9b12.json  6a71dbedc8403bd28fa76bd8b472597a8ecaab3af31151a2a3b72baeadd5e617
3906de3d.json  b4c20d433380e00840a75c6976ad0d0fabd80e052ab77b47422d64b1cae5f6dc
```

Direct tests must cover:

1. vertical `up` and `down` compaction;
2. horizontal `left` and `right` compaction;
3. preservation of non-background lane order and color counts;
4. unknown direction rejection;
5. candidate derivation returns the unique demonstrated candidate;
6. shape mismatch returns `NO_SHAPE_PRESERVING_GRAVITY`;
7. no-op demonstrations return no candidate with `NO_GRAVITY_COMPACTION`;
8. both pinned real tasks become trace-explained exact acceptances after integration.

Run RED and accept only:

```text
ModuleNotFoundError: No module named 'research.universal_core.holonomy_v2_2.gravity_compact'
```

Record `GRAVITY_COMPACT_RED.json` with run ID, source SHA, fixture integrity, two expected gains, frozen SHA, and `public_arc_evaluation_rerun: false`.

## Task 2 — Isolated module GREEN

Create `research/universal_core/holonomy_v2_2/gravity_compact.py`.

Interfaces:

```python
apply_gravity_compact(program: Mapping[str, Any], grid: Grid) -> Grid
gravity_compact_programs(demos: Sequence[tuple[Grid, Grid]]) -> tuple[tuple[Program, ...], str | None]
```

Implementation constraints:

- copy the input; never mutate it;
- canonical direction order: `up`, `down`, `left`, `right`;
- vertical directions compact columns; horizontal directions compact rows;
- preserve non-background order exactly;
- candidate background set is the intersection of source colors across demonstrations;
- candidate must fit every demonstration exactly;
- candidate must change at least one source;
- deterministic program order: background ascending, then canonical direction order;
- return `NO_DEMONSTRATION`, `NO_SHAPE_PRESERVING_GRAVITY`, or `NO_GRAVITY_COMPACTION` as applicable.

Run fixture plus direct tests excluding real integration assertions. Require frozen byte gate. Record `GRAVITY_COMPACT_MODULE_GREEN.json`.

## Task 3 — Guarded integration

Modify only through a fail-closed workflow:

- `grid_induction.py`
  - import `apply_gravity_compact`;
  - advance `_VERSION` from `grid-v2.2-13` to `grid-v2.2-14`;
  - dispatch kind `axis_gravity_compact`.
- `grid_mechanistic_runtime.py`
  - import `gravity_compact_programs`;
  - derive candidates after `block_reduce`;
  - register generator batch `gravity_compact` after `block_reduce`.

Run:

- all gravity tests;
- block-reduction tests;
- axis-collapse tests;
- palette-repeat tests;
- quadrant-mosaic tests;
- mirror/bbox/component-outlier/marker/mechanistic regression cluster;
- all V2.2 tests;
- frozen V2 integration tests;
- frozen byte gate.

On any failure, restore both shared runtime files and commit only diagnostics. On complete GREEN, commit shared files and `GRAVITY_COMPACT_GREEN.json`.

## Task 4 — Strict 1,000-task corpus gate

Use the immutable benchmark artifact from run `30929169392` and original V2.2 baseline report from run `30941837872`.

Require:

```text
rows                  1076
correct                 92
accepted                92
incorrect_attempts       0
failed                   0
ACCEPTED                92
AMBIGUOUS_PROGRAM        1
GRAMMAR_EXHAUSTED       983
trace_count            1000
parity_count           1000
```

Require the cumulative gain set to equal the prior 31 fixed-block gains plus exactly:

```text
1e0a9b12
3906de3d
```

For both new tasks require:

- terminal status `ACCEPTED`;
- a successful hidden execution with candidate kind `axis_gravity_compact`;
- selected candidate ID beginning `gravity_compact:`.

Recheck every prior primitive mechanism guard and `60b61512` ambiguity.

Generate `SHA256SUMS` after all writers close, verify it independently, then publish the complete artifact.

## Task 5 — Independent validation and sealing

Download the exact artifact by ID. Independently require:

- ZIP SHA equals GitHub artifact digest;
- 1,006 manifest entries and zero checksum failures;
- 1,000 task trace files;
- 1,000 compact/mechanistic parity checks and zero mismatches;
- exact 92/1/983 status boundary;
- zero lost baseline rows;
- 33 cumulative gain tasks;
- exact gravity task mechanism traces;
- preserved `60b61512` ambiguity.

Seal as:

```text
docs/evidence/arc_v2_2/TRAINING_GRAVITY_COMPACT_0015.json
```

Keep PR #40 draft and unmerged.
