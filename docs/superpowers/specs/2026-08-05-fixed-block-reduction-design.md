# Fixed-Block Reduction Design

## Objective

Add a generic ARC primitive that reduces a grid partitioned into fixed-size blocks to one output cell per block. The primitive targets two training-only grammar gaps while preserving all existing accepted mechanisms.

Development uses only the 1,000 ARC training tasks. The public ARC evaluation set is not rerun, and the frozen V2.1 core remains byte-identical.

## Training-only evidence

Exhaustive enumeration across all 1,000 training tasks found exactly two compatible grammar-exhausted tasks:

- `5614dbcf`: reduce 3-by-3 blocks by strict mode; an equivalent candidate ignores demonstrated noise color 5 and requires one remaining color per block;
- `68b67ca3`: reduce 2-by-2 blocks by the unique non-background color, using background 0.

For both tasks:

- every fitting candidate predicts the exact hidden target;
- fitting candidates form one hidden-output equivalence class;
- no wrong hidden output is completed;
- no already accepted task is compatible.

Expected cumulative result after integration:

- 90 correct and accepted rows out of 1,076;
- zero incorrect accepted rows;
- zero runner failures;
- one preserved `AMBIGUOUS_PROGRAM` task (`60b61512`);
- 985 `GRAMMAR_EXHAUSTED` rows.

## Program model

The new kind is `fixed_block_reduce`:

```json
{
  "kind": "fixed_block_reduce",
  "row_factor": 3,
  "col_factor": 3,
  "reducer": "strict_mode"
}
```

or:

```json
{
  "kind": "fixed_block_reduce",
  "row_factor": 2,
  "col_factor": 2,
  "reducer": "unique_non_background",
  "background": 0
}
```

Reducers:

- `strict_mode`: choose the unique most frequent color in the block; ties fail execution;
- `unique_non_background`: remove the configured background color, require at most one distinct remaining color, and return that color when present or the background when the block is otherwise empty.

## Candidate derivation

For every demonstration, output height and width must divide input height and width. The resulting row and column factors must be identical across all demonstrations and at least one factor must exceed one.

The generator then considers:

1. one `strict_mode` candidate;
2. one `unique_non_background` candidate for every color appearing in every demonstration input.

The generator exposes the structural candidates. The existing mechanistic fitting stage records all block executions and retains only candidates reproducing every demonstration target exactly.

When source/output dimensions do not define one stable block shape, the generator emits no candidates with `NO_STABLE_BLOCK_FACTORS`.

## Execution and safety

Execution partitions the source into non-overlapping blocks of `row_factor` by `col_factor`. Factors must divide the hidden input dimensions exactly. The output must remain within ARC bounds and cannot be empty.

Multiple fitting reducers remain explicit. Hidden-output consensus accepts only agreement and abstains on divergence. No reducer or background is preferred.

## Implementation

The isolated module is:

- `research/universal_core/holonomy_v2_2/block_reduce.py`

It exports:

```python
apply_block_reduce(program, grid) -> Grid
block_reduce_programs(demos) -> tuple[tuple[Program, ...], str | None]
```

The shared grammar advances from `grid-v2.2-12` to `grid-v2.2-13`.

## Observability

The existing mechanistic runtime records every reducer/background proposal, demonstration execution, fit decision, hidden execution, output class, and final decision. Compact and mechanistic results must remain exactly identical after removing the trace envelope.

## TDD and acceptance

1. Restore both fixtures byte-for-byte from immutable corpus artifact run `30929169392` and pin SHA-256 values.
2. Add direct tests for strict-mode success/tie failure, unique-non-background success/conflict failure, stable factor derivation, and exact acceptance of both real tasks.
3. Verify missing-module RED.
4. Implement and verify the isolated module.
5. Wire interpreter dispatch and mechanistic generator through a fail-closed workflow.
6. Run focused tests, all V2.2 tests, frozen V2 integration tests, and frozen-byte identity.
7. Run all 1,000 training tasks compact and mechanistic.
8. Require exactly the two new gains, no lost rows, zero incorrect attempts, 1,000 validated traces, 1,000 parity matches, and preserved `60b61512` ambiguity.
9. Checksum, publish, independently validate, and seal the artifact.

## Scope exclusions

This unit does not infer overlapping windows, variable block sizes within one task, weighted voting, arbitrary representative pixels, or task-ID rules. Those require separate evidence and TDD cycles.
