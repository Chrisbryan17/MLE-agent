# Palette-Cardinality Repeat Implementation Plan

> **Execution:** Use checkpointed strict TDD on `universal-core-arc-training-v2-2`. Do not touch the frozen V2.1 core or public ARC evaluation data.

**Goal:** Add `palette_cardinality_repeat` and convert exactly four training-only grammar gaps into correct acceptances.

## Constraints

- Training corpus only: 1,000 ARC tasks / 1,076 rows.
- Frozen path `research/universal_core/holonomy_v2` must remain byte-identical to `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- Public ARC evaluation rerun: prohibited.
- Expected cumulative metrics: 82 correct/accepted, zero incorrect attempts, zero failures.
- Expected statuses: ACCEPTED 82, AMBIGUOUS_PROGRAM 1, GRAMMAR_EXHAUSTED 993.
- Exact new gains: `a59b95c0`, `ac0a08a4`, `b91ae062`, `d4b1c2b1`.

### Task 1: Pinned fixtures and RED contract

**Create:**
- `research/universal_core/holonomy_v2_2/tests/fixtures/palette_repeat/{a59b95c0,ac0a08a4,b91ae062,d4b1c2b1}.json`
- `research/universal_core/holonomy_v2_2/tests/test_palette_repeat_fixtures.py`
- `research/universal_core/holonomy_v2_2/tests/test_palette_repeat.py`
- `.github/workflows/arc-palette-repeat-red.yml`

- Import each fixture byte-for-byte from the pinned ARC training corpus.
- Pin each fixture SHA-256 in a focused integrity test.
- Add direct execution tests for:
  - scale by `distinct_all`;
  - tile by `distinct_all`;
  - scale by `distinct_non_background`.
- Add candidate derivation tests requiring factor variation across demonstrations.
- Add a constant-factor test requiring `NO_FACTOR_VARIATION`.
- Add exact mechanistic acceptance tests for all four real tasks.
- Run focused RED and require only missing `palette_repeat` module.
- Commit RED evidence with exact run ID and task list.

### Task 2: Isolated implementation

**Create:** `research/universal_core/holonomy_v2_2/palette_repeat.py`

Implement:

```python
apply_palette_repeat(program, grid) -> Grid
palette_repeat_programs(demos) -> tuple[tuple[Program, ...], str | None]
```

- Supported operations: `scale`, `tile`.
- Supported statistics: `distinct_all`, `distinct_non_background`.
- Background candidates for the second statistic must appear in every demonstration input.
- Retain candidates only when all demonstrations execute exactly.
- Require at least two distinct demonstrated factors.
- Enforce factor >= 1 and ARC 30-by-30 bounds.
- Run direct module tests GREEN and commit the isolated module.

### Task 3: Guarded integration

**Modify:**
- `research/universal_core/holonomy_v2_2/grid_induction.py`
- `research/universal_core/holonomy_v2_2/grid_mechanistic_runtime.py`

**Create:** `.github/workflows/arc-palette-repeat-wire.yml`

- Import and dispatch `apply_palette_repeat` for kind `palette_cardinality_repeat`.
- Advance grammar version from `grid-v2.2-10` to `grid-v2.2-11`.
- Register generator batch prefix `palette_repeat:`.
- Run fixture, palette, quadrant, mirror, bbox, component-outlier, marker, mechanistic, and fixed scale/tile overlap tests.
- Run all V2.2 tests, frozen integration tests, and frozen byte gate.
- Commit shared files only on complete GREEN; otherwise restore them and commit diagnostics.

### Task 4: Strict 1,000-task corpus acceptance

**Create:** `.github/workflows/arc-palette-repeat-corpus.yml`

- Run all training tasks compact + mechanistic with parity verification.
- Validate all 1,000 traces.
- Require exact cumulative gain set of 23 tasks: prior 19 plus the four new IDs.
- Require metrics 82/1,076, zero wrong attempts/failures.
- Require status counts ACCEPTED 82, AMBIGUOUS_PROGRAM 1, GRAMMAR_EXHAUSTED 993.
- Require each new task select prefix `palette_repeat:` and retain prior primitive-selection guards.
- Require `60b61512` remain ambiguity-safe.
- Generate `SHA256SUMS` after writers close, verify it, and publish the exact artifact.

### Task 5: Independent validation and evidence sealing

**Create:** `docs/evidence/arc_v2_2/TRAINING_PALETTE_REPEAT_0012.json`

- Resolve artifact by exact evaluated SHA and workflow run.
- Independently verify all checksums and 1,000 traces.
- Recompute metrics, transitions, selected kinds, and per-task mechanisms.
- Commit run/job/artifact IDs and digests, report/diagnosis digests, event count, exact gained/lost rows, frozen byte gate, and `public_arc_evaluation_rerun: false`.
- Confirm PR #40 remains draft, open, and unmerged.
