# Palette-Cardinality Repeat Design

## Objective

Add a generic ARC primitive whose scale or tile factor is computed from the input grid's palette cardinality. The primitive targets four training-only grammar gaps while preserving all existing fixed scale and tile behavior.

Development uses only the 1,000 ARC training tasks. The public ARC evaluation set is not rerun, and the frozen V2.1 core remains byte-identical.

## Training-only evidence

An exhaustive scan of all 1,000 training tasks, including already accepted tasks, found exactly four compatible tasks:

- `a59b95c0`: whole-grid tiling by the number of distinct input colors;
- `ac0a08a4`: per-cell scaling by the number of distinct non-background colors;
- `b91ae062`: per-cell scaling by the number of distinct non-background colors;
- `d4b1c2b1`: per-cell scaling by the number of distinct input colors.

Each task has one fitting program, one hidden-output equivalence class, and an exact hidden target. The scan found no compatible already accepted task, no wrong completed hidden output, and no disagreement.

Expected cumulative training result after integration:

- 82 correct and accepted rows out of 1,076;
- zero incorrect accepted rows;
- zero runner failures;
- one preserved `AMBIGUOUS_PROGRAM` task (`60b61512`);
- 993 `GRAMMAR_EXHAUSTED` rows.

## Program model

The new kind is `palette_cardinality_repeat`:

```json
{
  "kind": "palette_cardinality_repeat",
  "operation": "scale",
  "statistic": "distinct_non_background",
  "background": 0
}
```

`operation` is one of:

- `scale`: replace each cell by a factor-by-factor constant block;
- `tile`: repeat the complete grid factor times vertically and horizontally.

`statistic` is one of:

- `distinct_all`: factor equals the number of distinct colors in the input;
- `distinct_non_background`: factor equals the number of distinct colors other than the demonstrated background.

The `background` field is present only for `distinct_non_background`.

## Candidate derivation

For each operation and statistic:

1. compute the statistic-derived factor independently for every demonstration input;
2. require factor >= 1 and a result no larger than ARC's 30-by-30 bounds;
3. execute the scale or tile operation;
4. retain the candidate only if every demonstration output is reproduced exactly;
5. require at least two distinct demonstrated factors.

The factor-variation requirement is the grammar-ownership boundary. A constant demonstrated factor provides no evidence that palette cardinality, rather than a fixed scale or tile program, controls the output. Such cases emit no dynamic candidate and remain owned by the existing grammar.

For `distinct_non_background`, background candidates are colors present in every demonstration input. Exact demonstration execution determines whether a candidate survives; no corner or modal heuristic is required.

## Execution and safety

At hidden execution time, the factor is recomputed from the hidden input. The operation rejects factor < 1 and outputs beyond 30-by-30. Multiple fitting candidates remain explicit and are handled by the existing hidden-output consensus. No statistic or operation is preferred without agreement.

The isolated implementation lives at:

- `research/universal_core/holonomy_v2_2/palette_repeat.py`

The shared grid grammar advances from `grid-v2.2-10` to `grid-v2.2-11`.

## Observability

The existing mechanistic runtime records this family through its standard lifecycle:

- generator start/end or skip reason;
- proposed operation/statistic/background programs;
- every demonstration execution and fit decision;
- hidden factor execution, failure, and output class;
- final selected candidate or abstention.

Compact and mechanistic results must remain exactly identical after removal of the trace envelope.

## TDD and acceptance

Strict sequence:

1. add immutable pinned fixtures for the four task IDs with SHA-256 integrity tests;
2. add direct scale/tile execution and factor-variation tests;
3. verify missing-module RED;
4. implement the isolated module;
5. verify module GREEN;
6. wire interpreter dispatch and mechanistic generator under a fail-closed workflow;
7. run focused tests, all V2.2 tests, frozen V2 integration tests, and frozen-byte identity;
8. run all 1,000 training tasks in compact and mechanistic modes;
9. require exactly the four new gains, no lost rows, zero incorrect attempts, 1,000 validated traces, 1,000 parity matches, and preserved `60b61512` ambiguity;
10. checksum, publish, independently validate, and seal the artifact evidence.

## Scope exclusions

This unit does not infer factors from cell counts, component counts, dimensions, task IDs, or target metadata. It does not add arbitrary block substitution or self-stamping. Those are separate families requiring independent evidence and TDD.
