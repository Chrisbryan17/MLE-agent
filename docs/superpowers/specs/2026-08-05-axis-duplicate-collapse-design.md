# Axis Duplicate Collapse Design

## Objective

Add a generic ARC primitive that compresses repeated rows and columns while preserving their first representative. The primitive targets six training-only grammar gaps and leaves all existing accepted mechanisms unchanged.

Development uses only the 1,000 ARC training tasks. The public ARC evaluation set is not rerun, and the frozen V2.1 core remains byte-identical.

## Training-only evidence

Exhaustive enumeration across all 1,000 training tasks found exactly six compatible grammar-exhausted tasks:

- `2dee498d`
- `746b3537`
- `7b7f7511`
- `ce8d95cc`
- `e1baa8a4`
- `eb5a1d5d`

Every fitting candidate produces the exact hidden target. All fitting scope/axis candidates agree on the six hidden outputs. The scan found:

- zero wrong completed hidden outputs;
- zero hidden-output disagreements;
- zero compatible already accepted tasks.

Expected cumulative training result after integration:

- 88 correct and accepted rows out of 1,076;
- zero incorrect accepted rows;
- zero runner failures;
- one preserved `AMBIGUOUS_PROGRAM` task (`60b61512`);
- 987 `GRAMMAR_EXHAUSTED` rows.

## Program model

The new kind is `axis_duplicate_collapse`:

```json
{
  "kind": "axis_duplicate_collapse",
  "scope": "adjacent_runs",
  "axes": "both"
}
```

`scope` is one of:

- `adjacent_runs`: replace each maximal consecutive run of identical rows or columns with its first member;
- `global_first`: retain the first occurrence of every distinct row or column and remove later duplicates, even when separated.

`axes` is one of:

- `rows`
- `columns`
- `both`

Rows and columns are compared as exact value tuples. Retained order is stable.

Row and column collapse commute: removing duplicate column vectors keeps one representative of every column-equivalence class and therefore preserves row equality; the symmetric argument applies to column equality after row collapse. `both` consequently has one canonical execution order.

## Candidate derivation

The generator considers all six scope/axis combinations. A candidate is exposed only when:

1. executing it changes at least one demonstration input;
2. its output dimensions do not exceed the corresponding input dimensions;
3. the candidate remains within ARC bounds.

The mechanistic runtime performs normal demonstration fitting and records every mismatch or acceptance. No scope or axis set is preferred.

This boundary avoids identity overlap. Training enumeration found no exact overlap with an existing accepted task.

## Hidden execution and ambiguity

The selected collapse operation is recomputed directly on each hidden input. When multiple candidates fit demonstrations:

- identical hidden outputs are deduplicated into one output class;
- divergent hidden outputs trigger the existing `AMBIGUOUS_PROGRAM` abstention.

## Implementation

The isolated module is:

- `research/universal_core/holonomy_v2_2/axis_collapse.py`

It exports:

```python
apply_axis_collapse(program, grid) -> Grid
axis_collapse_programs(demos) -> tuple[tuple[Program, ...], str | None]
```

The shared grid grammar advances from `grid-v2.2-11` to `grid-v2.2-12`.

## Observability

The existing mechanistic runtime records:

- generator start/end or skip reason;
- every scope/axis proposal;
- every demonstration execution and fit decision;
- every hidden execution;
- candidate deduplication and output-equivalence classes;
- final acceptance or ambiguity.

Compact and mechanistic results must remain exactly identical after removing the trace envelope.

## TDD and acceptance

1. Restore six fixtures byte-for-byte from immutable corpus artifact run `30929169392`.
2. Pin fixture SHA-256 values in a regression test.
3. Add direct tests for adjacent-run and global-first collapse, stable ordering, row-only/column-only/both modes, commutativity, and no-effect skip behavior.
4. Verify missing-module RED.
5. Implement the isolated module and verify module GREEN.
6. Wire interpreter dispatch and mechanistic generator through a fail-closed workflow.
7. Run focused tests, all V2.2 tests, frozen V2 integration tests, and frozen-byte identity.
8. Run all 1,000 training tasks compact and mechanistic.
9. Require exactly the six expected gains, no lost rows, zero incorrect attempts, 1,000 validated traces, 1,000 parity matches, and preserved `60b61512` ambiguity.
10. Checksum, publish, independently validate, and seal the artifact.

## Scope exclusions

This unit does not remove blank rows or columns merely because they contain a background color; it removes rows or columns only because they duplicate another row or column under the selected scope. It does not sort rows/columns, infer semantic separators, or use task identifiers.
