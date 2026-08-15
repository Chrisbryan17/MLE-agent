# Same-Color Straight-Line Connection Implementation Plan

**Goal:** Add `same_color_line_connect` as a generic V2.2 primitive that converts exactly four training gaps to exact acceptance while preserving every prior result and safety abstention.

## Global gates

- Training-only development on 1,000 ARC tasks / 1,076 hidden rows.
- No public ARC evaluation rerun.
- Frozen V2.1 byte identity at `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- No task-ID routing or preferred fitting candidate.
- Final exact metrics: 96 correct, 96 accepted, 0 incorrect attempts, 0 failures.
- Final statuses: 96 `ACCEPTED`, 1 `AMBIGUOUS_PROGRAM`, 979 `GRAMMAR_EXHAUSTED`.
- Cumulative gain set: prior 33 gains plus `1f876c06`, `22168020`, `22eb0ac0`, `ded97339`.

## Task 1 — Exact fixtures and RED contract

Pin exact vendor payloads under `tests/fixtures/line_connect/` and enforce known SHA-256 digests.

Create `test_line_connect_fixtures.py` and `test_line_connect.py` before production code.

Direct tests cover:

- horizontal connection;
- vertical connection;
- diagonal connection;
- original-anchor-only behavior;
- cross-color conflict rejection;
- unique demonstration derivation;
- shape mismatch skip;
- no-op skip;
- four real tasks as exact trace-explained acceptances after integration.

Hosted RED must fail only because `research.universal_core.holonomy_v2_2.line_connect` is missing, after fixture digests pass.

## Task 2 — Isolated module GREEN

Create `line_connect.py` with:

```python
apply_line_connect(program, grid)
line_connect_programs(demos)
```

Use original anchors only. Precompute segment claims. Reject different-color claim collisions and overwrites of existing different non-background cells. Canonical modes: horizontal, vertical, orthogonal, diagonal, all.

Candidate order: background ascending, then canonical mode order. Require exact demo fit and at least one changed demo.

Run fixture plus direct tests excluding real integration assertions. Require frozen byte gate and seal module GREEN evidence.

## Task 3 — Guarded integration

Fail-closed workflow modifications:

- `grid_induction.py`: import executor, `grid-v2.2-14` -> `grid-v2.2-15`, dispatch `same_color_line_connect`.
- `grid_mechanistic_runtime.py`: import generator, derive after gravity, append `line_connect` after `gravity_compact`.

Run line, gravity, block, axis, palette, quadrant, mirror, bbox, outlier, marker, mechanistic, full V2.2, frozen tests, and byte gate. Restore shared files on any failure.

## Task 4 — Strict corpus gate

Run all 1,000 training tasks with 1,000 validated traces and compact/mechanistic parity.

Require exact 37-task gain set, 96/1/979 status boundary, zero wrong accepts, no lost prior row, prior mechanism guard preservation, and `60b61512` ambiguity preservation.

For each new task require successful `same_color_line_connect` hidden execution and selected candidate prefix `line_connect:`.

Publish complete checksummed artifact only after every gate passes.

## Task 5 — Independent validation and sealing

Verify artifact ZIP digest, 1,006 manifest entries, zero checksum failures, 1,000 traces, 1,000 parity checks, exact metrics/statuses/gains, line mechanism traces, prior selector guards, and preserved ambiguity.

Seal as `docs/evidence/arc_v2_2/TRAINING_LINE_CONNECT_0016.json`. Keep PR #40 draft and unmerged.
