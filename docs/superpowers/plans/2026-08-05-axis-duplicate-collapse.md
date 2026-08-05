# Axis Duplicate Collapse Implementation Plan

**Goal:** Add `axis_duplicate_collapse` and convert exactly six ARC training grammar gaps into correct acceptances.

## Constraints

- Use only the 1,000 ARC training tasks / 1,076 rows.
- Do not rerun public ARC evaluation.
- Keep `research/universal_core/holonomy_v2` byte-identical to `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- Expected cumulative result: 88 correct/accepted, zero incorrect attempts/failures.
- Expected statuses: ACCEPTED 88, AMBIGUOUS_PROGRAM 1, GRAMMAR_EXHAUSTED 987.
- Exact new gains: `2dee498d`, `746b3537`, `7b7f7511`, `ce8d95cc`, `e1baa8a4`, `eb5a1d5d`.

### Task 1: Immutable fixtures and RED

Create:

- `research/universal_core/holonomy_v2_2/tests/fixtures/axis_collapse/*.json`
- `research/universal_core/holonomy_v2_2/tests/test_axis_collapse_fixtures.py`
- `research/universal_core/holonomy_v2_2/tests/test_axis_collapse.py`
- `.github/workflows/arc-axis-collapse-red.yml`

Restore the six JSON files directly from immutable corpus artifact run `30929169392`. Verify exact SHA-256 values. Test adjacent-run collapse, global-first collapse, stable first-occurrence ordering, row-only/column-only/both modes, row/column commutativity, no-effect generator skip, and exact mechanistic acceptance for all six tasks. Require missing-module RED and commit evidence.

### Task 2: Isolated module

Create `research/universal_core/holonomy_v2_2/axis_collapse.py` with:

```python
apply_axis_collapse(program, grid) -> Grid
axis_collapse_programs(demos) -> tuple[tuple[Program, ...], str | None]
```

Support scopes `adjacent_runs` and `global_first`; axes `rows`, `columns`, `both`. Use one canonical rows-then-columns execution for `both`; the operations commute. Expose candidates only when they change at least one demonstration. Return `NO_DUPLICATE_AXIS_REDUCTION` when none changes. Verify direct module tests GREEN.

### Task 3: Guarded integration

Modify `grid_induction.py` and `grid_mechanistic_runtime.py` under a fail-closed workflow:

- dispatch kind `axis_duplicate_collapse`;
- advance version `grid-v2.2-11` to `grid-v2.2-12`;
- add generator prefix `axis_collapse:`.

Run axis tests, palette, quadrant, mirror, bbox, component-outlier, marker, mechanistic tests, all V2.2 tests, frozen integration tests, and frozen-byte gate. Commit shared files only on complete GREEN.

### Task 4: Strict corpus gate

Create `.github/workflows/arc-axis-collapse-corpus.yml`.

Run all training tasks compact and mechanistic. Require:

- 1,000 validated traces and 1,000 parity matches;
- exact cumulative 29-task gain set: prior 23 plus the six new task IDs;
- metrics 88 correct/accepted, zero wrong attempts/failures;
- statuses ACCEPTED 88, AMBIGUOUS_PROGRAM 1, GRAMMAR_EXHAUSTED 987;
- each new task selects `axis_collapse:`;
- all prior primitive-selection guards remain stable;
- `60b61512` remains ambiguity-safe.

Generate and verify `SHA256SUMS`, then publish the exact artifact.

### Task 5: Independent validation and evidence

Independently verify all artifact checksums and traces, recompute metrics/transitions/mechanisms/event count, and commit:

- `docs/evidence/arc_v2_2/TRAINING_AXIS_COLLAPSE_0013.json`

Record exact run/job/artifact IDs and digests, frozen byte gate, and `public_arc_evaluation_rerun: false`. Confirm PR #40 remains draft and unmerged.
