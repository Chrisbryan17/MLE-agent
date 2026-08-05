# Dihedral Quadrant Mosaic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, fully traced `dihedral_quadrant_mosaic` ARC primitive that converts nine training-only grammar gaps into exact acceptances without changing any prior correct row or the frozen V2.1 core.

**Architecture:** A focused `quadrant_mosaic.py` module derives transform combinations by independently matching each source-sized output quadrant against shape-preserving dihedral transforms across all demonstrations. `grid_induction.py` executes the selected program, while `grid_mechanistic_runtime.py` exposes every structural hypothesis through the existing candidate lifecycle and hidden-output consensus.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, canonical JSON evidence, SHA-256 artifact manifests.

## Global Constraints

- Use only the 1,000 ARC training tasks for development and acceptance.
- Do not rerun the 120-task public ARC evaluation set.
- Do not modify `research/universal_core/holonomy_v2`; require byte identity against `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.
- Do not route by task ID or prefer one fitting transform without output consensus.
- Preserve compact/mechanistic result parity for all 1,000 training tasks.
- Expected cumulative corpus result: 78 correct and accepted rows, zero incorrect attempts, zero failures, one `AMBIGUOUS_PROGRAM`, and 997 `GRAMMAR_EXHAUSTED` rows.

---

### Task 1: Immutable fixtures and RED contract

**Files:**
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/0c786b71.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/3af2c5a8.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/46442a0e.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/62c24649.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/67e8384a.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/7953d61e.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/7fe24cdd.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/833dafe3.json`
- Create: `research/universal_core/holonomy_v2_2/tests/fixtures/quadrant_mosaic/ed98d772.json`
- Create: `research/universal_core/holonomy_v2_2/tests/test_quadrant_mosaic.py`
- Create: `.github/workflows/arc-quadrant-mosaic-red.yml`
- Evidence: `research/universal_core/holonomy_v2_2/evidence/QUADRANT_MOSAIC_RED.json`

**Interfaces:**
- Consumes: pinned ARC training JSON payloads.
- Produces: a focused test contract importing `apply_quadrant_mosaic` and `quadrant_mosaic_programs` from the intentionally absent module.

- [ ] **Step 1: Import the nine exact training payloads**

Extract the files without alteration from:

```text
research/universal_core/public_benchmarks/vendor/arc_agi_2/data/training/<task_id>.json
```

Verify each fixture retains both `train` and `test` arrays and contains exactly one hidden test row.

- [ ] **Step 2: Write direct execution tests**

Create tests covering the canonical reflected mosaic:

```python
program = {
    "kind": "dihedral_quadrant_mosaic",
    "top_left": "identity",
    "top_right": "reflect_columns",
    "bottom_left": "reflect_rows",
    "bottom_right": "rotate_180",
}
assert apply_quadrant_mosaic(program, [[1, 2], [3, 4]]) == [
    [1, 2, 2, 1],
    [3, 4, 4, 3],
    [3, 4, 4, 3],
    [1, 2, 2, 1],
]
```

Also require `ValueError` when a 16-by-16 source would produce a 32-by-32 output.

- [ ] **Step 3: Write deterministic derivation tests**

Use demonstrations whose four quadrants uniquely identify:

```python
(
    "identity",
    "reflect_columns",
    "reflect_rows",
    "rotate_180",
)
```

Assert `quadrant_mosaic_programs(demos)` returns one canonical program and `reason is None`. Add a non-double-dimension demonstration and require `programs == ()` with `reason == "OUTPUT_NOT_DOUBLE_SOURCE_SHAPE"`.

- [ ] **Step 4: Write exact real-task tests**

For each of the nine fixture IDs, build the public task using `train` as demonstrations and only `test[*].input` as hidden inputs. Require:

```python
result["predictions"] == [
    {"status": "ACCEPTED", "prediction": item["output"]}
    for item in payload["test"]
]
```

In mechanistic mode, require terminal status `ACCEPTED`, at least one successful hidden execution with `candidate_kind == "dihedral_quadrant_mosaic"`, and a selected candidate ID beginning with `quadrant_mosaic:`.

- [ ] **Step 5: Write ambiguity regression**

Use a demonstration source that is invariant under multiple transforms and an output composed from that symmetric source. Use an asymmetric hidden source. Require multiple fitting quadrant-mosaic candidates to produce at least two output classes and the final prediction status to be `AMBIGUOUS_PROGRAM`.

- [ ] **Step 6: Run focused RED**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests/test_quadrant_mosaic.py
```

Expected: collection fails only with:

```text
ModuleNotFoundError: No module named 'research.universal_core.holonomy_v2_2.quadrant_mosaic'
```

- [ ] **Step 7: Commit RED evidence**

The workflow must reject any other failure reason, then commit `QUADRANT_MOSAIC_RED.json` containing the source commit, run ID, exact command, expected missing module, nine expected gains, frozen-core SHA, and `public_arc_evaluation_rerun: false`.

---

### Task 2: Isolated dihedral transform and candidate engine

**Files:**
- Create: `research/universal_core/holonomy_v2_2/quadrant_mosaic.py`
- Test: `research/universal_core/holonomy_v2_2/tests/test_quadrant_mosaic.py`

**Interfaces:**
- Produces: `apply_quadrant_mosaic(program: Mapping[str, Any], grid: Grid) -> Grid`.
- Produces: `quadrant_mosaic_programs(demos: Sequence[tuple[Grid, Grid]]) -> tuple[tuple[Program, ...], str | None]`.

- [ ] **Step 1: Define canonical transform order**

```python
_TRANSFORM_ORDER = (
    "identity",
    "rotate_90",
    "rotate_180",
    "rotate_270",
    "reflect_columns",
    "reflect_rows",
    "reflect_main_diagonal",
    "reflect_anti_diagonal",
)
```

- [ ] **Step 2: Implement transform application**

Implement `_apply_transform(name, grid)` using copied lists. Reject unknown names. Quarter-turn and diagonal transforms may return swapped dimensions; caller validation determines whether they are shape-preserving.

- [ ] **Step 3: Implement quadrant splitting and execution**

`apply_quadrant_mosaic` must:

1. reject source height or width greater than 15;
2. apply the four named transforms in top-left, top-right, bottom-left, bottom-right order;
3. require every transformed grid to equal the source shape;
4. concatenate top quadrants row-wise, then bottom quadrants row-wise;
5. return a fresh grid.

- [ ] **Step 4: Implement demonstration-derived candidates**

For each demonstration:

```python
expected_shape = (2 * source_height, 2 * source_width)
```

Return `OUTPUT_NOT_DOUBLE_SOURCE_SHAPE` if any target differs. For each quadrant, intersect the transform names whose transformed source exactly matches the target quadrant across every demonstration. Return `NO_SUPPORTED_QUADRANT_TRANSFORM` if any intersection is empty. Otherwise return the Cartesian product in `_TRANSFORM_ORDER`, encoded as canonical program dictionaries.

- [ ] **Step 5: Run module tests GREEN**

Run:

```bash
python -m pytest -q research/universal_core/holonomy_v2_2/tests/test_quadrant_mosaic.py
```

Expected: direct module tests pass; full integration tests may still fail because dispatch is not wired.

- [ ] **Step 6: Commit isolated implementation**

```bash
git add research/universal_core/holonomy_v2_2/quadrant_mosaic.py
git commit -m "arc: add dihedral quadrant mosaic primitive"
```

---

### Task 3: Interpreter and mechanistic integration

**Files:**
- Modify: `research/universal_core/holonomy_v2_2/grid_induction.py`
- Modify: `research/universal_core/holonomy_v2_2/grid_mechanistic_runtime.py`
- Create: `.github/workflows/arc-quadrant-mosaic-wire.yml`
- Evidence: `research/universal_core/holonomy_v2_2/evidence/QUADRANT_MOSAIC_GREEN.json`

**Interfaces:**
- Consumes: `apply_quadrant_mosaic` and `quadrant_mosaic_programs`.
- Produces: grammar version `grid-v2.2-10` and generator prefix `quadrant_mosaic:`.

- [ ] **Step 1: Add interpreter dispatch**

In `grid_induction.py`, import `apply_quadrant_mosaic`, advance `_VERSION` from `grid-v2.2-9` to `grid-v2.2-10`, and add:

```python
if kind == "dihedral_quadrant_mosaic":
    return apply_quadrant_mosaic(program, grid)
```

- [ ] **Step 2: Add structural generator batch**

In `grid_mechanistic_runtime.py`, import `quadrant_mosaic_programs`, derive:

```python
quadrant_mosaic, quadrant_mosaic_reason = quadrant_mosaic_programs(demos)
```

and append:

```python
("quadrant_mosaic", quadrant_mosaic, quadrant_mosaic_reason)
```

to `_generator_batches` after `mirror_concat`.

- [ ] **Step 3: Syntax and diff gates**

Run:

```bash
python -m py_compile \
  research/universal_core/holonomy_v2_2/quadrant_mosaic.py \
  research/universal_core/holonomy_v2_2/grid_induction.py \
  research/universal_core/holonomy_v2_2/grid_mechanistic_runtime.py
git diff --check
```

- [ ] **Step 4: Run focused and cluster GREEN**

Run:

```bash
python -m pytest -q \
  research/universal_core/holonomy_v2_2/tests/test_quadrant_mosaic.py \
  research/universal_core/holonomy_v2_2/tests/test_mirror_concat.py \
  research/universal_core/holonomy_v2_2/tests/test_bbox_complete.py \
  research/universal_core/holonomy_v2_2/tests/test_component_outlier.py \
  research/universal_core/holonomy_v2_2/tests/test_marker_recolor.py \
  research/universal_core/holonomy_v2_2/tests/test_grid_mechanistic.py
python -m pytest -q research/universal_core/holonomy_v2_2/tests
```

- [ ] **Step 5: Run frozen gates**

```bash
PYTHONPATH=research python -m pytest -q \
  research/universal_core/holonomy_v2/tests/test_blind_adapter.py \
  research/universal_core/holonomy_v2/tests/test_engine.py
git diff --quiet 1d7c489bcdbff755d638b35ad47ce62bd4fe829d -- \
  research/universal_core/holonomy_v2
```

- [ ] **Step 6: Commit only on complete GREEN**

The guarded workflow restores both integration files on any failed gate. On success it commits the two integration files and `QUADRANT_MOSAIC_GREEN.json`, recording focused/full/frozen counts, run ID, expected nine-task delta, and byte-gate result.

---

### Task 4: Strict 1,000-task mechanistic corpus gate

**Files:**
- Create: `.github/workflows/arc-quadrant-mosaic-corpus.yml`
- Artifact: `arc-v2-2-quadrant-mosaic-${GITHUB_SHA}`

**Interfaces:**
- Consumes: immutable benchmark artifact from run `30929169392` and immutable V2.2 baseline report from run `30941837872`.
- Produces: `report.json`, `traces/*.json`, `traces/diagnosis.json`, `transitions.json`, `mechanisms.json`, `parity.json`, and `SHA256SUMS`.

- [ ] **Step 1: Run compact and mechanistic modes for all training tasks**

Call `run_training_corpus(..., mechanistic_dir=trace_dir, verify_parity=True)` and require 1,000 trace files, 1,000 validated traces, and parity count 1,000.

- [ ] **Step 2: Enforce exact cumulative metrics**

Require:

```python
report["metrics"]["rows"] == 1076
report["metrics"]["correct"] == 78
report["metrics"]["accepted"] == 78
report["metrics"]["incorrect_attempts"] == 0
report["metrics"]["failed"] == 0
report["status_counts"] == {
    "ACCEPTED": 78,
    "AMBIGUOUS_PROGRAM": 1,
    "GRAMMAR_EXHAUSTED": 997,
}
```

- [ ] **Step 3: Enforce exact cumulative gain set**

Require no lost baseline row and exactly these 19 gains over `e509650...`:

```text
0c786b71, 3aa6fb7a, 3af2c5a8, 46442a0e, 4c4377d9,
62c24649, 67e8384a, 6d0aefbc, 6d75e8bb, 6fa7a44f,
7953d61e, 7fe24cdd, 833dafe3, 8be77c9e, aabf363d,
b230c067, c9e6f938, e7639916, ed98d772
```

- [ ] **Step 4: Verify mechanism selection**

For each of the nine new tasks require terminal status `ACCEPTED`, at least one successful `dihedral_quadrant_mosaic` hidden execution, and selected candidate ID prefix `quadrant_mosaic:`. Recheck the prior marker, component-outlier, bounding-box, and mirror task prefixes. Require `60b61512` to remain `AMBIGUOUS_PROGRAM` with at least two bounding-box output classes.

- [ ] **Step 5: Build and verify artifact manifest**

Generate `SHA256SUMS` only after every writer closes, then run:

```bash
cd /tmp/arc-v2-2-quadrant-mosaic
sha256sum -c SHA256SUMS
```

- [ ] **Step 6: Publish the artifact**

Upload every report, trace, and manifest with 90-day retention. The workflow fails before publication on any metric, transition, trace, parity, or checksum mismatch.

---

### Task 5: Independent artifact validation and evidence sealing

**Files:**
- Create: `docs/evidence/arc_v2_2/TRAINING_QUADRANT_MOSAIC_0011.json`
- Optionally update: PR #40 body with the current primitive set and latest verified training result.

**Interfaces:**
- Consumes: exact successful corpus run and artifact ID.
- Produces: immutable repository evidence referencing the evaluated commit, run, artifact digest, report digest, diagnosis digest, counts, transitions, and mechanism trace digests.

- [ ] **Step 1: Download the exact artifact by ID**

Do not resolve by “latest.” Match workflow name, evaluated head SHA, artifact name, and artifact ID.

- [ ] **Step 2: Verify every checksum independently**

Run `sha256sum -c SHA256SUMS`, require 1,006 entries, parse all 1,000 task traces, and call `validate_trace` on each.

- [ ] **Step 3: Recompute acceptance assertions**

Independently read `report.json`, `transitions.json`, and `mechanisms.json`; require 78 correct/accepted, zero incorrect attempts, the exact 19-task gain set, nine quadrant-mosaic selected candidates, and preserved `60b61512` ambiguity.

- [ ] **Step 4: Commit sealed evidence**

Write `TRAINING_QUADRANT_MOSAIC_0011.json` with:

- candidate commit;
- workflow run and job IDs;
- artifact ID, name, size, and SHA-256 digest;
- checksum count and validation result;
- report and diagnosis digests;
- metrics and status counts;
- total trace event count;
- selected-kind and hidden-failure counts;
- exact gained/lost rows;
- per-task selected candidate and trace digest;
- frozen-core SHA and byte-gate result;
- `public_arc_evaluation_rerun: false`.

- [ ] **Step 5: Verify branch and PR state**

Confirm PR #40 remains open, draft, unmerged, and based on `universal-core-public-benchmark-adapters-v1`. Do not merge it.
