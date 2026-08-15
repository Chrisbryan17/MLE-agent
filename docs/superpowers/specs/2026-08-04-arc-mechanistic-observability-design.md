# ARC V2.2 Mechanistic Observability Design

## Status

Approved for implementation on `universal-core-arc-training-v2-2` under the standing instruction to use the recommended engineering choice without pausing for routine decisions.

## Purpose

Add deterministic, event-level observability to the complete ARC V2.2 grid-induction path so every hypothesis, demonstration check, rejection, hidden execution, equivalence class, abstention, and accepted prediction can be reconstructed exactly.

The trace system is diagnostic only. It must not change candidate generation, candidate ordering, predictions, status values, program digests, freeze digests, or prediction digests.

## Honesty boundary

“Complete mechanistic visibility” means complete visibility into every explicit decision and transformation performed by `research/universal_core/holonomy_v2_2` for grid tasks.

It does not claim visibility into:

- Python interpreter internals;
- operating-system or hardware execution;
- the immutable V2.1 implementation when a non-grid task is delegated to it.

Non-grid delegation is recorded as an explicit opaque boundary. The frozen V2.1 tree at `1d7c489bcdbff755d638b35ad47ce62bd4fe829d` remains byte-identical.

## Selected approach

Use dual execution modes:

1. **Compact mode** preserves the existing public result shape and low artifact cost.
2. **Mechanistic mode** runs the same inference path while collecting a complete deterministic event ledger.

All ARC remediation and training-corpus development runs use mechanistic mode. Compact and mechanistic outputs must pass a parity gate after removing trace-only fields.

This approach is preferred over always-on tracing because it preserves a small production-facing result while making full evidence mandatory during development.

## Architecture

### 1. Deterministic trace recorder

Add `research/universal_core/holonomy_v2_2/mechanistic_trace.py` with a recorder that:

- emits monotonically numbered events;
- canonicalizes every event using sorted-key JSON;
- rejects non-JSON-safe values;
- seals the ledger with SHA-256;
- records the trace schema as `mechanistic-grid-trace-v1`;
- excludes `task_id` from the trace-content digest so task-name invariance remains testable;
- includes a separate task-bound envelope digest for artifact integrity.

The recorder is passive. It cannot decide whether a candidate fits or alter any program.

### 2. Single inference path

Extend the entry point to:

```python
run_public_task_v2_2(task, engine, *, mechanistic=False)
```

Both modes execute one shared inference path. Mechanistic mode provides a recorder to that path; compact mode provides no recorder. No duplicate inference implementation is allowed.

### 3. Candidate provenance

Every candidate receives:

- a canonical program representation;
- a program digest;
- a generator name;
- a generator-local ordinal;
- the exact structural parameters used to construct it.

Candidate generators must expose all structurally valid candidates rather than silently filtering them internally. Demonstration fitting is centralized so every proposal receives one visible fit decision.

Existing generator families covered by this requirement are:

- fixed geometric transforms;
- color mapping;
- scale and tiling;
- crop;
- component-rank recoloring;
- panel Boolean combination;
- enclosed-region operations;
- component-area selection;
- every later primitive.

For derived generators that cannot construct a candidate, the trace records a generator skip with an exact reason.

### 4. Demonstration execution ledger

For every proposed candidate and every demonstration, record exactly one of:

- successful execution with the complete output grid and output digest;
- typed execution failure with exception class and message.

For successful outputs, record the comparison result against the target. A mismatch records:

- source and target dimensions;
- produced dimensions;
- all differing coordinates when dimensions match;
- complete produced and target grids.

Each candidate then receives exactly one terminal fit decision:

- `FITS_ALL_DEMOS`;
- `DEMO_MISMATCH`;
- `DEMO_EXECUTION_FAILED`.

Duplicate canonical programs are recorded before one representative is retained.

### 5. Hidden execution ledger

Every fitting, deduplicated candidate receives exactly one execution result for every hidden input:

- complete output and digest; or
- typed execution failure.

Successful complete output batches are grouped by canonical batch digest. The trace records every equivalence-class member and its program digest.

### 6. Final decision ledger

The final event records one exact outcome:

- `GRAMMAR_EXHAUSTED` when no candidate fits all demonstrations;
- `EXECUTION_FAILED` when fitting candidates exist but none complete all hidden inputs;
- `AMBIGUOUS_PROGRAM` when completed candidates form multiple output classes;
- `ACCEPTED` when all completed candidates form one output class.

For an accepted result, the trace records:

- the complete agreeing program-digest set;
- the deterministic minimum-digest selected program;
- output-batch digest;
- public program, freeze, and prediction digests.

For an abstention, it records the exact candidate and failure counts that caused it.

## Completeness invariants

Mechanistic mode fails closed if any invariant is violated:

1. Every proposed candidate has one terminal demonstration-fit decision.
2. Every fitting deduplicated candidate has one terminal hidden-batch result.
3. Every successful hidden batch belongs to exactly one output equivalence class.
4. Every final-decision reference points to an event or digest already present in the ledger.
5. Event ordinals are contiguous and deterministic.
6. Replaying the same task produces a byte-identical trace.
7. Changing only `task_id` preserves the trace-content digest.
8. Compact and mechanistic modes produce identical non-trace results.

## Training-corpus integration

Extend `run_training_corpus` with optional mechanistic output parameters. In mechanistic mode it writes one canonical trace file per task and stores only trace references in the sealed aggregate report:

- trace schema;
- trace-content digest;
- task-bound envelope digest;
- relative artifact path;
- event count;
- terminal decision.

The full grids remain in per-task traces rather than inflating the aggregate report.

Add a deterministic corpus diagnosis that aggregates only trace facts, including:

- rejection counts by generator and cause;
- hidden execution failures by exception type and candidate kind;
- ambiguity counts and competing candidate kinds;
- grammar-exhaustion counts by generator coverage;
- accepted counts by selected primitive.

Targets used for scoring remain outside the model trace and are never fed back into induction. A separate post-score comparison may classify correct and incorrect predictions but must not modify the mechanistic ledger.

## Workflow and evidence

Update the training workflow so every development corpus run publishes:

- compact aggregate report;
- per-task mechanistic traces;
- corpus diagnosis;
- parity report;
- checksum manifest.

Required gates are:

- focused trace tests;
- all V2.2 tests;
- frozen V2 integration tests;
- frozen V2 byte-diff gate;
- deterministic replay gate;
- compact/mechanistic parity gate;
- full 1,000-task ARC training run;
- zero newly incorrect accepted rows;
- no public ARC evaluation rerun.

## Root-cause evidence already identified

The current two `EXECUTION_FAILED` training tasks are understood mechanistically and will become the first trace-driven capability upgrades after observability is green.

### `aabf363d`

The only fitting candidate is a literal color map. The demonstrations use an isolated marker cell to specify a new object color, but the hidden object uses an unseen source color. Hidden execution raises `KeyError("unmapped grid cell")`.

The generic missing mechanism is marker-directed recoloring with marker removal, not another literal mapping entry.

### `b230c067`

Two component-rank programs fit the demonstrations. The hidden input introduces a component-area rank not seen in the demonstrations. Both candidates raise `KeyError("unmapped component rank")`.

The generic missing mechanism is binary extreme-versus-other component recoloring, not exact rank enumeration.

These facts are provisional local analysis until reproduced by the new event ledger. Implementation begins only after the trace confirms them.

## Subsequent trace-driven primitives

After the observability layer proves parity and completeness, capability work proceeds one primitive at a time under strict TDD:

1. marker-directed object recoloring;
2. binary component-extreme recoloring;
3. bounding-box completion using preserve-existing interior or outline modes.

Each primitive must show:

- a focused RED fixture;
- trace-confirmed root cause;
- smallest generic implementation;
- focused GREEN;
- complete V2.2 and frozen-core gates;
- full training-corpus comparison;
- no lost exact tasks and no incorrect accepted rows.

## Non-goals

This unit does not:

- modify frozen V2.1;
- add task-ID routing;
- use ARC public-evaluation targets for development;
- claim neural activation interpretability for a symbolic program enumerator;
- change scoring policy;
- improve coverage before trace parity is proven.

## Acceptance criteria

The design is complete when:

- all V2.2 grid candidates and decisions are reconstructible from a sealed trace;
- a completeness checker proves there are no unrecorded candidate or execution paths;
- trace replay is deterministic;
- compact and mechanistic outputs are identical apart from trace references;
- the full ARC training artifact contains one valid trace per task;
- the frozen V2.1 byte gate passes;
- the two current execution failures are reproduced with their exact exception mechanisms in the new traces.
