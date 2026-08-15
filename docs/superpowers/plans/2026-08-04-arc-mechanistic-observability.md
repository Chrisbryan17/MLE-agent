# ARC V2.2 Mechanistic Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, complete mechanistic traces for every ARC V2.2 grid-induction decision while proving compact-mode parity and reproducing the exact causes of the two current hidden-execution failures.

**Architecture:** A passive content-addressed recorder stores canonical programs, grids, and output batches once and emits ordered events that reference those objects. Candidate generators expose structurally valid programs without internal fitting; one shared inference path owns demonstration fitting, hidden execution, equivalence grouping, and final decisions in both compact and mechanistic modes. Training runs execute compact and mechanistic passes, verify parity, write one sealed trace per task, and aggregate trace-only diagnosis.

**Tech Stack:** Python 3.12, standard-library `dataclasses`, `hashlib`, and `json`; pytest; GitHub Actions; immutable ARC-AGI-2 training artifact.

## Global Constraints

- Work only on branch `universal-core-arc-training-v2-2`.
- Do not modify `research/universal_core/holonomy_v2`.
- Frozen V2.1 must remain byte-identical to `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- Use only the 1,000 ARC-AGI-2 training tasks for iterative development.
- Do not rerun ARC public evaluation.
- Do not add task-ID routing or target-informed model behavior.
- Mechanistic tracing must not alter statuses, predictions, program digests, freeze digests, or prediction digests.
- Every coherent unit uses focused RED, focused GREEN, affected-cluster GREEN, frozen-core gates, and an atomic commit.
- Full-corpus acceptance requires zero newly incorrect accepted rows and no lost exact tasks relative to the 59/1,076 baseline.

## File structure

- Create `research/universal_core/holonomy_v2_2/mechanistic_trace.py`: canonical object store, event recorder, trace sealing, trace validation, trace writing.
- Create `research/universal_core/holonomy_v2_2/trace_diagnosis.py`: deterministic aggregation of trace facts only.
- Create `research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py`: recorder, sealing, determinism, validation, and task-ID invariance tests.
- Create `research/universal_core/holonomy_v2_2/tests/test_trace_diagnosis.py`: aggregate diagnosis tests.
- Modify `research/universal_core/holonomy_v2_2/panel_combine.py`: expose unfiltered structural enumeration.
- Modify `research/universal_core/holonomy_v2_2/region_fill.py`: expose unfiltered structural enumeration.
- Modify `research/universal_core/holonomy_v2_2/component_select.py`: expose unfiltered structural enumeration.
- Modify `research/universal_core/holonomy_v2_2/grid_induction.py`: central fitting, tracing, hidden execution, equivalence grouping, final decision, and dual-mode entry point.
- Modify `research/universal_core/holonomy_v2_2/training_eval.py`: optional trace directory, compact/mechanistic parity, trace references, diagnosis.
- Modify `research/universal_core/holonomy_v2_2/tests/test_grid_induction.py`: dual-mode parity, complete candidate lifecycle, deterministic replay, opaque delegate boundary.
- Modify `research/universal_core/holonomy_v2_2/tests/test_training_eval.py`: per-task traces, parity failure containment, references, diagnosis.
- Modify `.github/workflows/arc-training-corpus-v2-2.yml`: mandatory mechanistic corpus run and artifact publication.
- Create `research/universal_core/holonomy_v2_2/evidence/MECHANISTIC_TRACE_TDD.json`: immutable RED/GREEN and corpus evidence references after hosted verification.

---

### Task 1: Deterministic recorder and completeness validator

**Files:**
- Create: `research/universal_core/holonomy_v2_2/mechanistic_trace.py`
- Create: `research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py`

**Interfaces:**
- Consumes: JSON-safe Python mappings, task ID, terminal decision.
- Produces:
  - `TraceRecorder(task_id: str)`
  - `TraceRecorder.store(value: Any) -> str`
  - `TraceRecorder.emit(event: str, **data: Any) -> None`
  - `TraceRecorder.seal(terminal_status: str) -> dict[str, Any]`
  - `validate_trace(trace: Mapping[str, Any]) -> None`
  - `write_trace(trace: Mapping[str, Any], path: Path | str) -> Path`

- [ ] **Step 1: Write failing recorder tests**

Create tests with these exact contracts:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.universal_core.holonomy_v2_2.mechanistic_trace import (
    TraceRecorder,
    validate_trace,
    write_trace,
)


def complete_trace(task_id: str = "alpha") -> dict[str, object]:
    recorder = TraceRecorder(task_id)
    program_ref = recorder.store({"kind": "identity"})
    grid_ref = recorder.store([[1]])
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit(
        "demo_execution",
        candidate_id="fixed:0000",
        demo_index=0,
        outcome="MATCH",
        output_ref=grid_ref,
        target_ref=grid_ref,
    )
    recorder.emit(
        "candidate_fit_decision",
        candidate_id="fixed:0000",
        decision="FITS_ALL_DEMOS",
    )
    recorder.emit(
        "hidden_execution",
        candidate_id="fixed:0000",
        hidden_index=0,
        outcome="SUCCEEDED",
        output_ref=grid_ref,
    )
    recorder.emit(
        "hidden_batch_decision",
        candidate_id="fixed:0000",
        decision="COMPLETED",
        batch_ref=recorder.store([[[1]]]),
    )
    recorder.emit(
        "equivalence_class",
        batch_ref=recorder.store([[[1]]]),
        candidate_ids=["fixed:0000"],
    )
    recorder.emit(
        "final_decision",
        status="ACCEPTED",
        candidate_ids=["fixed:0000"],
    )
    return recorder.seal("ACCEPTED")


def test_trace_is_deterministic_and_task_id_independent() -> None:
    first = complete_trace("alpha")
    second = complete_trace("beta")
    assert first["trace_digest"] == second["trace_digest"]
    assert first["envelope_digest"] != second["envelope_digest"]
    assert json.dumps(first, sort_keys=True) == json.dumps(complete_trace("alpha"), sort_keys=True)


def test_validator_rejects_missing_candidate_terminal_event() -> None:
    recorder = TraceRecorder("bad")
    program_ref = recorder.store({"kind": "identity"})
    recorder.emit(
        "candidate_proposed",
        candidate_id="fixed:0000",
        generator="fixed",
        program_digest=program_ref,
        program_ref=program_ref,
    )
    recorder.emit("final_decision", status="GRAMMAR_EXHAUSTED", candidate_ids=[])
    with pytest.raises(ValueError, match="terminal demonstration decision"):
        recorder.seal("GRAMMAR_EXHAUSTED")


def test_write_trace_emits_canonical_json(tmp_path: Path) -> None:
    trace = complete_trace()
    path = write_trace(trace, tmp_path / "trace.json")
    assert path.read_text(encoding="utf-8").endswith("\n")
    validate_trace(json.loads(path.read_text(encoding="utf-8")))
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py
```

Expected: collection failure because `holonomy_v2_2.mechanistic_trace` does not exist.

- [ ] **Step 3: Implement the minimal recorder**

Implement these rules:

```python
_TRACE_SCHEMA = "mechanistic-grid-trace-v1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()
```

`TraceRecorder.store` must canonicalize the value, use its SHA-256 as the key, and reject a hash collision with unequal canonical bytes. `emit` must append `{"ordinal": n, "event": event, ...}` with contiguous zero-based ordinals. `seal` must build:

```python
{
    "schema": _TRACE_SCHEMA,
    "task_id": task_id,
    "objects": {digest: value, ...},
    "events": [...],
    "event_count": len(events),
    "terminal_status": terminal_status,
    "trace_digest": digest({"schema": schema, "objects": objects, "events": events, "terminal_status": terminal_status}),
    "envelope_digest": digest({"task_id": task_id, "trace_digest": trace_digest}),
}
```

`validate_trace` must verify digests, contiguous ordinals, object references, candidate lifecycle completeness, hidden lifecycle completeness for fitting non-duplicate candidates, equivalence-class membership, and exactly one final decision matching `terminal_status`.

- [ ] **Step 4: Run focused GREEN**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py
```

Expected: all recorder tests pass.

- [ ] **Step 5: Run the existing V2.2 cluster**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests
```

Expected: existing tests plus recorder tests pass.

- [ ] **Step 6: Commit**

```bash
git add research/universal_core/holonomy_v2_2/mechanistic_trace.py research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py
git commit -m "arc: add deterministic mechanistic trace ledger"
```

---

### Task 2: Expose every structural candidate before fitting

**Files:**
- Modify: `research/universal_core/holonomy_v2_2/panel_combine.py:panel_candidates`
- Modify: `research/universal_core/holonomy_v2_2/region_fill.py:region_candidates`
- Modify: `research/universal_core/holonomy_v2_2/component_select.py:component_select_candidates`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_panel_combine.py`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_region_fill.py`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_component_select.py`

**Interfaces:**
- Consumes: normalized demonstration `(source_grid, target_grid)` pairs.
- Produces:
  - `panel_programs(demos) -> tuple[tuple[Program, ...], str | None]`
  - `region_programs(demos) -> tuple[tuple[Program, ...], str | None]`
  - `component_select_programs(demos) -> tuple[tuple[Program, ...], str | None]`
- Compatibility wrappers `*_candidates` remain available and retain their currently filtered behavior until Task 3 switches the grid path.

- [ ] **Step 1: Write failing enumeration tests**

Add one test per module proving an intentionally non-fitting structural program is returned. Example panel contract:

```python
def test_panel_programs_expose_structural_hypotheses_before_fit() -> None:
    demos = (([[1, 0, 9, 2, 0]], [[4, 0]]),)
    programs, reason = panel_combine.panel_programs(demos)
    assert reason is None
    assert len(programs) > len(panel_combine.panel_candidates(demos))
    assert any(item["predicate"] == "xor" for item in programs)
```

Region and component-selection tests must similarly assert structural enumeration is larger than the fitting subset. Add skip-reason tests for invalid target-color cardinality or unavailable background evidence.

- [ ] **Step 2: Run the three focused files and verify RED**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_panel_combine.py \
  research/universal_core/holonomy_v2_2/tests/test_region_fill.py \
  research/universal_core/holonomy_v2_2/tests/test_component_select.py
```

Expected: failures because `panel_programs`, `region_programs`, and `component_select_programs` do not exist.

- [ ] **Step 3: Implement unfiltered enumerators**

Move only structural loops into the new functions. They must not call `_fits`. Return an exact reason when no structural family can be formed, using stable values such as:

- `TARGET_COLOR_CARDINALITY_NOT_TWO`
- `NO_BACKGROUND_CANDIDATE`
- `NO_STRUCTURAL_PROGRAM`

Keep current `*_candidates` wrappers as:

```python
def panel_candidates(demos: Sequence[tuple[Grid, Grid]]) -> tuple[Program, ...]:
    programs, _ = panel_programs(demos)
    return tuple(program for program in programs if _fits(program, demos))
```

Apply the same pattern to region and component-selection modules.

- [ ] **Step 4: Run focused GREEN and the V2.2 cluster**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_panel_combine.py \
  research/universal_core/holonomy_v2_2/tests/test_region_fill.py \
  research/universal_core/holonomy_v2_2/tests/test_component_select.py
python -m pytest -q research/universal_core/holonomy_v2_2/tests
```

Expected: all tests pass with unchanged public predictions.

- [ ] **Step 5: Commit**

```bash
git add \
  research/universal_core/holonomy_v2_2/panel_combine.py \
  research/universal_core/holonomy_v2_2/region_fill.py \
  research/universal_core/holonomy_v2_2/component_select.py \
  research/universal_core/holonomy_v2_2/tests/test_panel_combine.py \
  research/universal_core/holonomy_v2_2/tests/test_region_fill.py \
  research/universal_core/holonomy_v2_2/tests/test_component_select.py
git commit -m "arc: expose structural grid hypotheses"
```

---

### Task 3: Integrate complete tracing into the shared inference path

**Files:**
- Modify: `research/universal_core/holonomy_v2_2/grid_induction.py:_candidate_programs,_fits,run_public_task_v2_2`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_grid_induction.py`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_component_rank.py`

**Interfaces:**
- Consumes:
  - `TraceRecorder | None`
  - structural program batches from Task 2.
- Produces:
  - `run_public_task_v2_2(task, engine, *, mechanistic: bool = False) -> dict[str, Any]`
  - mechanistic result field `mechanistic_trace` only when requested.

- [ ] **Step 1: Write failing dual-mode and lifecycle tests**

Add contracts for:

```python
def without_trace(result: dict[str, object]) -> dict[str, object]:
    copied = dict(result)
    copied.pop("mechanistic_trace", None)
    return copied


def test_mechanistic_mode_has_exact_compact_parity() -> None:
    value = task(
        [{"input": [[0, 1]], "output": [[2, 3]]}],
        [[[1, 0]]],
        "parity",
    )
    compact = grid_induction.run_public_task_v2_2(value, engine=None)
    traced = grid_induction.run_public_task_v2_2(value, engine=None, mechanistic=True)
    assert without_trace(traced) == compact
    validate_trace(traced["mechanistic_trace"])


def test_trace_records_rejected_and_fitting_candidates() -> None:
    value = task(
        [{"input": [[1, 2]], "output": [[2, 1]]}],
        [[[3, 4]]],
        "candidate-ledger",
    )
    trace = grid_induction.run_public_task_v2_2(value, None, mechanistic=True)["mechanistic_trace"]
    events = trace["events"]
    proposed = [item for item in events if item["event"] == "candidate_proposed"]
    terminal = [item for item in events if item["event"] == "candidate_fit_decision"]
    assert len(proposed) == len(terminal)
    assert {item["decision"] for item in terminal} >= {"FITS_ALL_DEMOS", "DEMO_MISMATCH"}


def test_hidden_key_error_is_recorded_with_type_and_message() -> None:
    value = make_component_rank_task_that_introduces_an_unseen_hidden_rank()
    result = grid_induction.run_public_task_v2_2(value, None, mechanistic=True)
    failures = [
        item for item in result["mechanistic_trace"]["events"]
        if item["event"] == "hidden_execution" and item["outcome"] == "FAILED"
    ]
    assert failures
    assert all(item["exception_type"] == "KeyError" for item in failures)
    assert all("unmapped component rank" in item["exception_message"] for item in failures)
```

Also add deterministic replay, task-ID-independent `trace_digest`, accepted-equivalence membership, ambiguity membership, grammar exhaustion, and non-grid `delegate_boundary` tests.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_grid_induction.py \
  research/universal_core/holonomy_v2_2/tests/test_component_rank.py \
  research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py
```

Expected: `TypeError` for the missing `mechanistic` keyword and missing trace events.

- [ ] **Step 3: Replace opaque fitting with one traced evaluator**

Introduce internal records with deterministic candidate IDs. The central evaluator must:

1. emit `generator_start`;
2. emit `generator_skip` or `candidate_proposed` for every program;
3. execute every demonstration for every proposal;
4. store source, target, produced grids, and batches in the trace object store;
5. emit exact mismatch coordinates or typed failures;
6. emit one `candidate_fit_decision` per proposal;
7. deduplicate fitting programs by program digest and emit `candidate_duplicate`;
8. execute every hidden row for every fitting representative;
9. emit one `hidden_batch_decision` per representative;
10. emit one `equivalence_class` per successful batch;
11. emit one `final_decision` and seal the trace.

The public result must be constructed before trace attachment. Attach the sealed trace only after public digests are final.

Do not catch exceptions outside the existing `KeyError`, `TypeError`, and `ValueError` boundary.

- [ ] **Step 4: Run focused GREEN**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_grid_induction.py \
  research/universal_core/holonomy_v2_2/tests/test_component_rank.py \
  research/universal_core/holonomy_v2_2/tests/test_mechanistic_trace.py
```

Expected: all focused tests pass.

- [ ] **Step 5: Run complete V2.2 and frozen integration gates**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests
PYTHONPATH=research python -m pytest -q \
  research/universal_core/holonomy_v2/tests/test_blind_adapter.py \
  research/universal_core/holonomy_v2/tests/test_engine.py
git diff --quiet 1d7c489bcdbff755d638b35ad47ce62bd4fe829d -- research/universal_core/holonomy_v2
```

Expected: all tests pass and the frozen diff command exits zero.

- [ ] **Step 6: Commit**

```bash
git add \
  research/universal_core/holonomy_v2_2/grid_induction.py \
  research/universal_core/holonomy_v2_2/tests/test_grid_induction.py \
  research/universal_core/holonomy_v2_2/tests/test_component_rank.py
git commit -m "arc: trace complete grid inference path"
```

---

### Task 4: Add corpus trace output, parity, and diagnosis

**Files:**
- Create: `research/universal_core/holonomy_v2_2/trace_diagnosis.py`
- Create: `research/universal_core/holonomy_v2_2/tests/test_trace_diagnosis.py`
- Modify: `research/universal_core/holonomy_v2_2/training_eval.py:run_training_corpus`
- Modify: `research/universal_core/holonomy_v2_2/tests/test_training_eval.py`

**Interfaces:**
- Consumes:
  - `run_training_corpus(..., mechanistic_dir: Path | str | None = None, verify_parity: bool = False)`
  - sealed per-task traces.
- Produces:
  - per-report `mechanistic_trace` reference containing `path`, `trace_digest`, `envelope_digest`, `event_count`, and `terminal_status`;
  - `build_trace_diagnosis(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]`;
  - canonical `diagnosis.json` when tracing is enabled.

- [ ] **Step 1: Write failing evaluator and diagnosis tests**

Add tests proving:

- two fixture tasks write `a.json` and `b.json` traces in sorted order;
- the aggregate report excludes full event arrays;
- each trace reference matches the file digest and envelope digest;
- compact/mechanistic mismatch raises `RuntimeError("mechanistic parity failure")`;
- diagnosis counts hidden `KeyError` failures by candidate kind and accepted decisions by selected kind;
- scoring targets are not present in any trace object unless they also occur as demonstration targets.

Use a fake runner accepting `mechanistic=` and returning a minimal valid trace from Task 1.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_training_eval.py \
  research/universal_core/holonomy_v2_2/tests/test_trace_diagnosis.py
```

Expected: import failure for `trace_diagnosis` and unexpected keyword errors for `mechanistic_dir`.

- [ ] **Step 3: Implement traced corpus execution**

When `mechanistic_dir` is set:

1. run compact mode;
2. run mechanistic mode;
3. remove only `mechanistic_trace` from the mechanistic result and compare exact equality when `verify_parity=True`;
4. validate and write the trace to `<mechanistic_dir>/<task_id>.json`;
5. use the compact result for scoring;
6. append a digest-only trace reference to the task report;
7. build and write `diagnosis.json` after all tasks.

Seal the aggregate report only after trace references and diagnosis digest are present.

`trace_diagnosis.py` must derive counts exclusively from events and object references. It must not inspect ARC test outputs or scoring metrics.

- [ ] **Step 4: Run focused GREEN and all V2.2 tests**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_training_eval.py \
  research/universal_core/holonomy_v2_2/tests/test_trace_diagnosis.py
python -m pytest -q research/universal_core/holonomy_v2_2/tests
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add \
  research/universal_core/holonomy_v2_2/trace_diagnosis.py \
  research/universal_core/holonomy_v2_2/training_eval.py \
  research/universal_core/holonomy_v2_2/tests/test_trace_diagnosis.py \
  research/universal_core/holonomy_v2_2/tests/test_training_eval.py
git commit -m "arc: publish mechanistic corpus diagnosis"
```

---

### Task 5: Publish full mechanistic training evidence and confirm root causes

**Files:**
- Modify: `.github/workflows/arc-training-corpus-v2-2.yml`
- Create: `research/universal_core/holonomy_v2_2/evidence/MECHANISTIC_TRACE_TDD.json`
- Create after successful run: `docs/evidence/arc_v2_2/TRAINING_MECHANISTIC_0006.json`

**Interfaces:**
- Consumes: pinned corpus artifact from workflow run `30929169392` and the Task 4 evaluator.
- Produces: one artifact containing `report.json`, `console-summary.json`, `traces/*.json`, `traces/diagnosis.json`, `parity.json`, and `SHA256SUMS`.

- [ ] **Step 1: Add a hosted RED evidence commit before implementation is wired**

Commit the focused tests from Tasks 1–4 before production implementation and allow `.github/workflows/arc-training-v2-2.yml` to record the expected failure. Capture run ID, failing test names, and exact reason in `MECHANISTIC_TRACE_TDD.json`.

- [ ] **Step 2: Update the corpus workflow**

Change the Python invocation to:

```python
trace_dir = Path('/tmp/arc-v2-2-training/traces')
report = run_training_corpus(
    vendor,
    HolonomyEngine(SearchConfig()),
    run_label='arc-v2-2-training-' + os.environ['GITHUB_SHA'][:12],
    candidate_commit=os.environ['GITHUB_SHA'],
    mechanistic_dir=trace_dir,
    verify_parity=True,
)
```

After writing the report, create `parity.json` with task count and zero mismatches, then generate a sorted SHA-256 manifest over every artifact file except the manifest itself. Fail unless exactly 1,000 task trace files exist and every trace validates.

- [ ] **Step 3: Run hosted focused GREEN**

Push a normal branch commit so `.github/workflows/arc-training-v2-2.yml` runs. Require:

- all V2.2 tests pass;
- frozen V2 integration tests pass;
- frozen V2 byte gate passes.

Record run ID and commit SHA in `MECHANISTIC_TRACE_TDD.json`.

- [ ] **Step 4: Run the full 1,000-task mechanistic corpus**

Require the corpus workflow to finish successfully and publish its artifact. Download and independently verify:

```bash
sha256sum -c SHA256SUMS
python - <<'PY'
import json
from pathlib import Path
from research.universal_core.holonomy_v2_2.mechanistic_trace import validate_trace

root = Path('traces')
paths = sorted(path for path in root.glob('*.json') if path.name != 'diagnosis.json')
assert len(paths) == 1000
for path in paths:
    validate_trace(json.loads(path.read_text(encoding='utf-8')))
PY
```

- [ ] **Step 5: Compare against the 59/1,076 baseline**

Require:

- 1,076 rows evaluated;
- at least 59 correct accepted rows;
- zero incorrect accepted rows;
- no previously exact task lost;
- status changes explained by trace events rather than instrumentation side effects.

Tracing itself is rejected if any compact prediction or digest changes.

- [ ] **Step 6: Confirm the two existing execution failures from trace evidence**

For task `aabf363d`, require at least one hidden failure event with:

```json
{
  "exception_type": "KeyError",
  "exception_message": "'unmapped grid cell'",
  "candidate_kind": "color_map"
}
```

For task `b230c067`, require hidden failure events for both fitting representatives with:

```json
{
  "exception_type": "KeyError",
  "exception_message": "'unmapped component rank'",
  "candidate_kind": "component_rank_color"
}
```

Do not implement either capability fix in this task. Seal the confirmed mechanisms first.

- [ ] **Step 7: Write immutable evidence**

Create `TRAINING_MECHANISTIC_0006.json` containing:

- candidate commit;
- focused RED and GREEN run IDs;
- full corpus run ID;
- artifact ID and digest;
- report digest;
- diagnosis digest;
- trace count and total event count;
- compact/mechanistic parity count;
- frozen-core commit;
- unchanged training metrics;
- exact trace references for `aabf363d` and `b230c067`;
- explicit statement that public ARC evaluation was not rerun.

- [ ] **Step 8: Commit the workflow and evidence**

```bash
git add \
  .github/workflows/arc-training-corpus-v2-2.yml \
  research/universal_core/holonomy_v2_2/evidence/MECHANISTIC_TRACE_TDD.json \
  docs/evidence/arc_v2_2/TRAINING_MECHANISTIC_0006.json
git commit -m "arc: seal mechanistic training evidence"
```

## Plan self-review

- Spec coverage: recorder, complete candidate lifecycle, hidden execution, equivalence classes, final decisions, parity, deterministic replay, task-ID invariance, training traces, diagnosis, workflow artifact, frozen boundary, and both root-cause confirmations are assigned to explicit tasks.
- Scope: capability upgrades are intentionally excluded from this plan and begin only after Task 5 seals root-cause evidence.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation instruction, or unnamed error-handling step remains.
- Type consistency: `TraceRecorder`, `validate_trace`, `write_trace`, `mechanistic`, `mechanistic_dir`, `verify_parity`, and `build_trace_diagnosis` use the same names and signatures throughout.
