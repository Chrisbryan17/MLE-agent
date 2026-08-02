# Universal Core Holonomy V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an additive holonomy-native task learner that grows typed programs from demonstrations, rejects candidates with failed closed-path checks, preserves V1, passes Run 001 regression, and freezes before a fresh Run 002.

**Architecture:** V2 lives in `research/universal_core/holonomy_v2/`. It uses immutable typed fibers, a closed expression grammar, a connection graph, explicit closed paths, typed residual reports, cost-guided candidate growth, counterexample-guided refinement, and a provider-neutral proposal tier. V1 and blind protocol V1 remain byte-identical.

**Tech Stack:** Python 3.12, standard library, `pytest==9.0.2`, existing canonical and task-contract modules, GitHub Actions.

## Global Constraints

- Base commit: `0194001e82721cd9081aca16bb1c04f34d1c56aa`.
- Production code is additive under `research/universal_core/holonomy_v2/`.
- V1 and blind protocol files remain byte-identical.
- Run 001 assets are test-only; production imports from them are forbidden.
- Hidden inputs never enter induction or candidate ranking.
- No dynamic Python evaluation, row-key answer maps, task-id routing, target ledgers, or unbounded execution.
- Tier D and Tier H are scored separately.
- Every accepted candidate has mandatory closed-path evidence.
- Every bound is recorded in evidence.
- Run 002 is generated only after the V2 code identity is frozen.
- New files may not contain the owner-defined forbidden three-letter sequence.

## File Map

Production:
`__init__.py`, `types.py`, `fibers.py`, `program.py`, `instructions.py`, `atoms.py`, `grammar.py`, `connection.py`, `loops.py`, `residuals.py`, `search.py`, `refine.py`, `proposer.py`, `engine.py`, `blind_adapter.py`, `security.py`, `cli.py`.

Tests:
focused test files for every production module, plus `tests/regression/run001/`, `test_run001_regression.py`, `test_run001_mutations.py`, and `tests/run_v2_gates.py`.

Workflow:
`.github/workflows/universal-core-holonomy-v2.yml`.

---

### Task 1: Contracts and bounds

**Files**
- Create `research/universal_core/holonomy_v2/types.py`
- Create `research/universal_core/holonomy_v2/__init__.py`
- Create `research/universal_core/holonomy_v2/tests/test_types.py`

**Produces**
`FiberKind`, `NodeKind`, `FailureCode`, `EngineLimits`, `SearchConfig`, `Abstention`, `SearchStats`.

- [ ] Write failing tests:

```python
def test_default_limits_are_bounded():
    limits = EngineLimits()
    assert limits.max_depth == 6
    assert limits.max_candidates == 50_000
    assert limits.max_steps == 100_000

def test_nonpositive_limit_is_rejected():
    with pytest.raises(ValueError):
        EngineLimits(max_depth=0)
```

- [ ] Run:
`PYTHONPATH=research python -m pytest research/universal_core/holonomy_v2/tests/test_types.py -q`
Expected: import failure.

- [ ] Implement frozen dataclasses, enum values, canonical `to_data`, and positive-bound checks.

- [ ] Re-run and commit:
`git commit -m "feat: add holonomy v2 contracts"`.

---

### Task 2: Typed fibers

**Files**
- Create `fibers.py`
- Create `tests/test_fibers.py`

**Produces**
`FiberSchema.infer`, `FiberValue.of`, `TransportSignature`, `Observation`, `schema_distance`.

- [ ] Write failing tests for scalar, record, table, graph, empty sequence, and round trip.

```python
def test_record_schema_ignores_key_order():
    assert FiberSchema.infer({"b": 2, "a": 1}) == FiberSchema.infer({"a": 4, "b": 9})

def test_graph_schema_requires_edges():
    assert FiberSchema.infer({"nodes": ["a"], "edges": []}).kind is FiberKind.GRAPH
```

- [ ] Run the test file and verify red state.
- [ ] Implement structural schema inference; booleans are not integers; keys are canonical; metadata is absent.
- [ ] Re-run and commit:
`git commit -m "feat: add typed fibers"`.

---

### Task 3: Immutable program graph

**Files**
- Create `program.py`
- Create `tests/test_program.py`

**Produces**
`Program.parse`, `Program.run`, `Program.digest`, `Program.cost`, `EvaluationContext`.

- [ ] Write failing tests for order→project, filter→aggregate, graph→label, conditional, canonical digest, invalid node, and step bound.

```python
def test_order_then_project():
    program = Program.parse({
        "kind": "compose",
        "parts": [
            {"kind": "order", "field": "score", "descending": True},
            {"kind": "project", "field": "id"},
        ],
    })
    assert program.run([{"id": "a", "score": 1}, {"id": "b", "score": 4}]) == ["b", "a"]
```

- [ ] Run and verify red state.
- [ ] Implement input, literal, field, index, compose, map, filter, project, order, aggregate, compare, boolean, conditional, label-map, graph-reachable, shortest-path, and format nodes.
- [ ] Every node validates types, has fixed cost, uses step accounting, and serializes canonically.
- [ ] Run and commit:
`git commit -m "feat: add typed program graph"`.

---

### Task 4: Instruction hints and task atoms

**Files**
- Create `instructions.py`, `atoms.py`
- Create `tests/test_instructions.py`, `tests/test_atoms.py`

**Produces**
`InstructionHints`, `parse_instruction_hints`, `AtomPool`, `derive_atoms`.

- [ ] Write failing tests for phase, priority, exception, capacity, direction, tie-break, label definitions, field paths, constants, and symbols.

```python
def test_hint_parser():
    hints = parse_instruction_hints(
        "After phase two, red overrides blue. Capacity is at most 7."
    )
    assert hints.numeric_constants == (7,)
    assert hints.priority_terms == (("red", "blue"),)
```

- [ ] Run and verify red state.
- [ ] Implement weak hints; demonstrations and loop checks remain authoritative.
- [ ] Derive recursive field paths, exact constants, labels, symbol tables, comparisons, and pair relations. Exclude task ids.
- [ ] Run and commit:
`git commit -m "feat: derive task atoms"`.

---

### Task 5: Grammar and connection graph

**Files**
- Create `grammar.py`, `connection.py`
- Create `tests/test_grammar.py`, `tests/test_connection.py`

**Produces**
`GrammarRule`, `TaskGrammar`, `build_task_grammar`, `TransportEdge`, `ConnectionGraph`.

- [ ] Write failing tests proving depth-two growth can create order→project and graph→label without a named family template.
- [ ] Write a type-invalid composition test.
- [ ] Write provenance and deterministic path-order tests.
- [ ] Run and verify red state.
- [ ] Implement bounded typed growth and behavior-based deduplication.
- [ ] Implement schema vertices, transport edges, path composition, provenance, and bounded path search.
- [ ] Run and commit:
`git commit -m "feat: add grammar and connection graph"`.

---

### Task 6: Closed paths and residuals

**Files**
- Create `loops.py`, `residuals.py`
- Create `tests/test_loops.py`, `tests/test_residuals.py`

**Produces**
`LoopKind`, `ClosedPath`, `LoopSet`, `ResidualEntry`, `ResidualReport`, `build_loops`, `check_residuals`.

- [ ] Write failing tests for replay, direct-vs-decomposed, adapter round trip, key rename, key permutation, row permutation, state cycle, and priority-order agreement.
- [ ] Write a passing zero-residual case and a rejected nonzero mandatory case.
- [ ] Run and verify red state.
- [ ] Implement exact, rational, structural, label, constraint, and path-disagreement distances.
- [ ] Mandatory failure rejects the candidate; optional residuals affect rank.
- [ ] Run and commit:
`git commit -m "feat: add closed path residuals"`.

---

### Task 7: Deterministic candidate search

**Files**
- Create `search.py`
- Create `tests/test_search.py`

**Produces**
`CandidateRecord`, `SearchResult`, `search_candidates`.

- [ ] Write failing tests for order→project discovery, graph→label discovery, mandatory-loop pruning, ambiguity, and budget exhaustion.
- [ ] Run and verify red state.
- [ ] Implement a deterministic priority queue ranked by cost, mandatory status, optional residual, replay error, then digest.
- [ ] Cache intermediate demonstration outputs.
- [ ] Bound depth, candidates, and steps; record every prune reason.
- [ ] Run and commit:
`git commit -m "feat: add deterministic program search"`.

---

### Task 8: New-rule nodes and refinement

**Files**
- Modify `program.py`, `grammar.py`
- Create `refine.py`
- Create `tests/test_refine.py`
- Extend `tests/test_program.py`

**Produces**
finite-state step, repeated step, priority rule, bounded assignment, bounded schedule, `Counterexample`, `Refinement`, `refine_grammar`.

- [ ] Write failing tests for phase-dependent symbols, exception-before-default rules, board transitions, and canonical two-resource schedules.
- [ ] Write a failed-loop test that adds a context state key.
- [ ] Run and verify red state.
- [ ] Implement deterministic bounded enumeration with canonical tie-breaking.
- [ ] Refinement may add state, split a symbol by context, add a priority edge, require a composition boundary, reject an inverse, or activate bounded search. It may not add row-specific data.
- [ ] Run and commit:
`git commit -m "feat: add new-rule induction"`.

---

### Task 9: Engine and blind adapter

**Files**
- Create `engine.py`, `blind_adapter.py`
- Create `tests/test_engine.py`, `tests/test_blind_adapter.py`

**Produces**
`HolonomyEngine`, `InductionResult`, `PredictionBatch`, `EngineEvidence`, `run_public_task_v2`.

- [ ] Write a failing freeze-before-hidden-prediction test.
- [ ] Write a test proving hidden inputs are absent from the induction call.
- [ ] Run and verify red state.
- [ ] Implement: induction view → fibers/atoms → grammar/graph → search/refinement → loop checks → one candidate or typed abstention → freeze → hidden execution.
- [ ] Evidence includes source identity, config, atom/grammar/graph digests, counts, prune data, program digest, residual digest, freeze digest, and prediction digest.
- [ ] Run and commit:
`git commit -m "feat: add holonomy v2 engine"`.

---

### Task 10: Run 001 regression and mutation gates

**Files**
- Create `tests/regression/run001/public_challenge.json`
- Create `tests/regression/run001/private_reveal.json`
- Create `tests/regression/run001/family_generator.py`
- Create `tests/regression/run001/manifest.json`
- Create `tests/test_run001_regression.py`
- Create `tests/test_run001_mutations.py`

- [ ] Record source artifact and file digests in the manifest.
- [ ] Add original gate:

```python
def test_run001_all_rows():
    score = evaluate_run001(HolonomyEngine(regression_config()))
    assert score.correct == 600
    assert score.attempted == 600
    assert score.coverage == 1.0
```

- [ ] Run and retain the expected red evidence on the six prior failure families.
- [ ] Add deterministic mutations: task id, field names, constants, labels, symbol alphabet, graph names, board size, duration, capacity, and demonstration order.
- [ ] Add mutation gate: raw accuracy ≥ 0.95 and coverage ≥ 0.95 across 40 seeds.
- [ ] Improve only generic production capability, with a focused red-green test for every change.
- [ ] Run all V2 tests and commit:
`git commit -m "test: add run001 regression gates"`.

---

### Task 11: Provider-neutral Tier H

**Files**
- Create `proposer.py`, `tests/test_proposer.py`
- Modify `engine.py`

**Produces**
`ProgramProposal`, `ProposalBackend`, `JsonProposalBackend`, `HolonomyEngine.induce_with_proposer`.

- [ ] Write failing tests rejecting unknown node kinds, extra fields, undeclared constants, and type mismatch.
- [ ] Write a test proving a valid proposal passes the same mandatory loops.
- [ ] Run and verify red state.
- [ ] Implement strict JSON parsing. The provider sees only induction data, allowed node schemas, and bounds.
- [ ] Record tier as `D` or `H`; Tier D remains runnable without provider access.
- [ ] Run and commit:
`git commit -m "feat: add verified proposal tier"`.

---

### Task 12: Security, CLI, CI, and full gate

**Files**
- Create `security.py`, `cli.py`
- Create `tests/test_security.py`, `tests/run_v2_gates.py`
- Create `.github/workflows/universal-core-holonomy-v2.yml`
- Create `checkpoints/2026-08-02/HOLONOMY_V2_BASELINE.md`

- [ ] Write failing scans for regression imports, dynamic evaluation, task-id routing, row-key maps, target fields, and the owner-defined forbidden sequence.
- [ ] Implement AST import checks and source-token checks.
- [ ] Add CLI commands: `induce`, `predict`, `regression`, `evidence`, `scan`.
- [ ] Full gate runs frozen V1 byte comparison, V1 tests, blind protocol tests, V2 tests, original Run 001, mutation suite, replay, security scan, and evidence manifest.
- [ ] Create CI with Python 3.12 and pinned pytest. Upload JUnit, regression summaries, residual summaries, scan data, environment data, and SHA-256 manifests.
- [ ] Run:
`PYTHONPATH=research python -m universal_core.holonomy_v2.tests.run_v2_gates --output artifacts/holonomy-v2`
Expected: zero failed gates.
- [ ] Commit:
`git commit -m "ci: add holonomy v2 full gate"`.

---

### Task 13: Freeze and Run 002

**Files**
- Create `checkpoints/<freeze-date>/HOLONOMY_V2_FREEZE.md`
- Do not commit Run 002 generator data or targets before submission sealing.

- [ ] Record exact commit, tree digest, source digests, dependencies, bounds, and passing CI run.
- [ ] Re-run all gates on that exact head; do not change files after the final green run.
- [ ] Create Run 002 outside the repository after freeze: at least 16 families, 800 hidden rows, 6 new rule systems, balanced demonstrations, new terminology, and ambiguity cases.
- [ ] Execute Tier D once without network; seal the submission.
- [ ] Execute Tier H once through the declared provider interface; seal the submission.
- [ ] Reveal, score, audit, and publish all results regardless of score.
- [ ] Move Run 002 into regression status only after reveal. Any later code identity requires another fresh suite.

## Self-Review

Spec coverage:
Tasks 1–2 cover fibers; 3 and 8 cover the program graph; 4 atoms; 5 grammar and connection; 6 loops and residuals; 7 search; 8 refinement; 9 engine and freeze boundary; 10 Run 001; 11 Tier H; 12 security and CI; 13 Run 002.

Type consistency:
The plan uses one `Program`, `TaskGrammar`, `ResidualReport`, `SearchConfig`, and `HolonomyEngine`. Tier values are `D` and `H`.

Placeholder scan:
No deferred markers, vague test steps, or undefined public interfaces remain.
