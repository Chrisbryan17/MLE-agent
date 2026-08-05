# Fixed-Block Reduction Implementation Plan

**Goal:** Add `fixed_block_reduce` and convert exactly two ARC training grammar gaps into correct acceptances.

## Constraints

- Training only: 1,000 tasks / 1,076 rows.
- Public ARC evaluation rerun prohibited.
- Frozen V2.1 bytes unchanged against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- Expected cumulative metrics: 90 correct/accepted, zero incorrect attempts/failures.
- Expected statuses: ACCEPTED 90, AMBIGUOUS_PROGRAM 1, GRAMMAR_EXHAUSTED 985.
- Exact new gains: `5614dbcf`, `68b67ca3`.

### Task 1: Fixtures and RED

Create fixture integrity and behavior tests under `tests/fixtures/block_reduce`, `test_block_reduce_fixtures.py`, and `test_block_reduce.py`. Restore source JSON directly from immutable artifact run `30929169392`. Test strict mode, tie failure, unique non-background, conflicting non-background failure, stable factor derivation, unstable-factor skip, and exact mechanistic acceptance for both tasks. Verify missing-module RED and commit evidence.

### Task 2: Isolated module

Create `block_reduce.py` exporting:

```python
apply_block_reduce(program, grid) -> Grid
block_reduce_programs(demos) -> tuple[tuple[Program, ...], str | None]
```

Implement stable block factors, `strict_mode`, and `unique_non_background`. Enforce divisibility, nonempty output, and ARC bounds. Verify direct module GREEN.

### Task 3: Guarded integration

Modify `grid_induction.py` and `grid_mechanistic_runtime.py` only through a fail-closed workflow:

- dispatch `fixed_block_reduce`;
- advance `grid-v2.2-12` to `grid-v2.2-13`;
- register generator prefix `block_reduce:`.

Run block, axis, palette, quadrant, mirror, bbox, component-outlier, marker, mechanistic, full V2.2, frozen integration, and byte gates. Commit shared files only on complete GREEN.

### Task 4: Strict corpus gate

Run all 1,000 training tasks compact and mechanistic. Require exactly 31 cumulative gains, including `5614dbcf` and `68b67ca3`; 90 correct/accepted; zero incorrect attempts/failures; statuses 90/1/985; 1,000 traces and parity matches; prior primitive guards unchanged; `60b61512` ambiguity preserved. Build and verify `SHA256SUMS`, then publish the exact artifact.

### Task 5: Independent validation

Independently verify all checksums and traces, recompute metrics/transitions/mechanisms/event count, and seal `docs/evidence/arc_v2_2/TRAINING_BLOCK_REDUCE_0014.json`. Record exact run/job/artifact IDs and digests, frozen byte gate, and `public_arc_evaluation_rerun: false`. Keep PR #40 draft and unmerged.
