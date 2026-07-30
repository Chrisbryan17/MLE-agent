# Universal Core V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a benchmark-agnostic reasoning compiler that infers one unknown task schema from 3–20 labeled demonstrations, synthesizes and verifies a reusable solver, freezes it, and executes it unchanged on hidden rows.

**Architecture:** Add a new `research/universal_core/` package beside the preserved BBEH work. The package normalizes benchmark inputs, induces typed task specifications, synthesizes either trusted operator programs or constrained MiniLang programs, verifies candidates, seals the accepted solver, executes hidden rows, and emits an immutable audit package. Existing BBEH source, fitted ledgers, workflows, checkpoints, and artifacts remain untouched.

**Tech Stack:** Python 3.12, standard-library dataclasses and JSON, pytest, z3-solver for bounded constraint templates, GitHub Actions, SHA-256 canonical sealing. Generated fallback programs run in a purpose-built interpreter; the implementation must never use `eval()` or `exec()`.

## Global Constraints

- Immutable archive branch: `archive/universal-bbeh-dual-track-4520-2026-07-28`.
- Immutable archive commit: `a0c099a41c85f267ca6323235a019b2052107873`.
- Universal Core development is additive; do not delete or rewrite archived source, workflows, checkpoints, manifests, predictions, or evidence.
- Each batch contains exactly one unknown task schema.
- Each batch contains 3–20 labeled demonstrations and one or more hidden unlabeled rows.
- Benchmark names, task identifiers, filenames, row indices, and inert metadata must not influence induction, synthesis, or solver selection.
- Hidden targets must be rejected by the normalizer and remain unavailable before prediction sealing.
- No input-hash answer mappings, row-specific exceptions, target-informed correction ledgers, or manual solver routing are permitted in Universal Core execution.
- Solver source, specification, verification evidence, runtime configuration, dependencies, seeds, and limits must be frozen before hidden execution.
- First-attempt predictions are immutable; revisions create separate attempt directories.
- Report raw accuracy, coverage, attempted-row accuracy, coverage-adjusted accuracy, abstention rate, induction success, verification pass rate, deterministic replay rate, task-family breakdowns, and resource usage.
- Generated fallback code is represented in MiniLang and interpreted without network, filesystem, subprocess, reflection, package installation, or host-object access.
- All implementation tasks use TDD and end with an atomic commit.

---

## File Map

Create the following focused package structure:

```text
research/universal_core/
  __init__.py                 public exports and version
  canonical.py                canonical JSON and SHA-256 helpers
  contracts.py                task/result/status dataclasses
  normalizer.py               external JSON -> canonical TaskPackage
  ir.py                       typed task-specification IR
  operators.py                trusted operator registry and execution
  programs.py                 OperatorProgram and MiniLangProgram contracts
  induction.py                task hypothesis generation and proposal backends
  templates.py                reusable algorithmic template synthesis
  minilang.py                 constrained generated-code interpreter
  verification.py             checks, counterexamples, and evidence
  selection.py                deterministic candidate ranking and abstention
  sealing.py                  freeze manifests and immutable attempt writes
  runner.py                   end-to-end pipeline
  metrics.py                  evaluation summaries
  cli.py                      command-line entry point
  archive_guard.py            archive identity and non-deletion checks
  tests/
    conftest.py
    test_archive_guard.py
    test_contracts.py
    test_normalizer.py
    test_ir.py
    test_operators.py
    test_induction.py
    test_templates.py
    test_minilang.py
    test_verification.py
    test_selection.py
    test_sealing.py
    test_runner.py
    test_metrics.py
    test_anti_cheating.py
    test_security.py
    test_fresh_instances.py
    generators.py
    fixtures/
      sort_records.json
      affine_numbers.json
      keyword_relation.json
.github/workflows/universal-core-v1.yml
research/universal_core/checkpoints/2026-07-29/UNIVERSAL_CORE_V1_BASELINE.md
```

No file in `research/universal_validation/` is modified by this plan.

---

### Task 1: Establish the additive package and archive guard

**Files:**
- Create: `research/universal_core/__init__.py`
- Create: `research/universal_core/archive_guard.py`
- Create: `research/universal_core/tests/test_archive_guard.py`

**Interfaces:**
- Produces: `ARCHIVE_BRANCH: str`, `ARCHIVE_COMMIT: str`.
- Produces: `verify_archive(repo_root: Path, run: Callable[..., CompletedProcess[str]] = subprocess.run) -> ArchiveVerification`.
- Produces: `ArchiveVerification(commit_resolves: bool, branch_matches: bool, deleted_protected_paths: tuple[str, ...])`.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
from universal_core.archive_guard import ARCHIVE_COMMIT, verify_archive


def test_archive_commit_is_the_verified_head() -> None:
    assert ARCHIVE_COMMIT == "a0c099a41c85f267ca6323235a019b2052107873"


def test_archive_guard_reports_deleted_protected_paths(tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        command = " ".join(args)
        if "rev-parse" in command:
            return type("R", (), {"returncode": 0, "stdout": ARCHIVE_COMMIT + "\n", "stderr": ""})()
        return type("R", (), {
            "returncode": 0,
            "stdout": "research/universal_validation/semantic_dual_track_v1.py\n",
            "stderr": "",
        })()

    result = verify_archive(tmp_path, run=fake_run)
    assert result.commit_resolves is True
    assert result.branch_matches is True
    assert result.deleted_protected_paths == (
        "research/universal_validation/semantic_dual_track_v1.py",
    )
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `python -m pytest research/universal_core/tests/test_archive_guard.py -q`

Expected: collection fails because `universal_core.archive_guard` does not exist.

- [ ] **Step 3: Implement the minimal archive guard**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

ARCHIVE_BRANCH = "archive/universal-bbeh-dual-track-4520-2026-07-28"
ARCHIVE_COMMIT = "a0c099a41c85f267ca6323235a019b2052107873"
PROTECTED_PREFIXES = (
    "research/universal_validation/",
    ".github/workflows/universal-semantic-dual-track-v1.yml",
)


@dataclass(frozen=True)
class ArchiveVerification:
    commit_resolves: bool
    branch_matches: bool
    deleted_protected_paths: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.commit_resolves and self.branch_matches and not self.deleted_protected_paths


def verify_archive(repo_root: Path, run: Callable = subprocess.run) -> ArchiveVerification:
    resolve = run(
        ["git", "rev-parse", ARCHIVE_COMMIT], cwd=repo_root,
        text=True, capture_output=True, check=False,
    )
    branch = run(
        ["git", "rev-parse", f"refs/remotes/origin/{ARCHIVE_BRANCH}"], cwd=repo_root,
        text=True, capture_output=True, check=False,
    )
    deleted = run(
        ["git", "diff", "--name-only", "--diff-filter=D", f"{ARCHIVE_COMMIT}...HEAD", "--", *PROTECTED_PREFIXES],
        cwd=repo_root, text=True, capture_output=True, check=False,
    )
    return ArchiveVerification(
        commit_resolves=resolve.returncode == 0 and resolve.stdout.strip() == ARCHIVE_COMMIT,
        branch_matches=branch.returncode == 0 and branch.stdout.strip() == ARCHIVE_COMMIT,
        deleted_protected_paths=tuple(line for line in deleted.stdout.splitlines() if line),
    )
```

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest research/universal_core/tests/test_archive_guard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/__init__.py research/universal_core/archive_guard.py research/universal_core/tests/test_archive_guard.py
git commit -m "test: guard verified reasoning archive"
```

---

### Task 2: Define canonical task and result contracts

**Files:**
- Create: `research/universal_core/canonical.py`
- Create: `research/universal_core/contracts.py`
- Create: `research/universal_core/tests/test_contracts.py`

**Interfaces:**
- Produces: `canonical_json_bytes(value: object) -> bytes` and `sha256_hex(value: bytes) -> str`.
- Produces: `Demonstration`, `OutputSchema`, `TaskPackage`, `PredictionRow`, `AttemptResult`, and `FailureStatus`.
- `TaskPackage.compute_digest()` excludes inert metadata and includes instructions, demonstrations, hidden inputs, and output schema.

- [ ] **Step 1: Write failing contract tests**

```python
import pytest
from universal_core.contracts import Demonstration, OutputSchema, TaskPackage


def test_task_package_accepts_three_to_twenty_demonstrations() -> None:
    demos = tuple(Demonstration(input=i, output=i + 1) for i in range(3))
    package = TaskPackage("add one", demos, (20,), OutputSchema(kind="integer"), {"task_name": "ignored"})
    assert len(package.package_digest) == 64


def test_task_package_rejects_hidden_targets() -> None:
    demos = tuple(Demonstration(input=i, output=i) for i in range(3))
    with pytest.raises(ValueError, match="hidden target"):
        TaskPackage("identity", demos, ({"input": 1, "target": 1},), OutputSchema(kind="integer"), {})


def test_inert_metadata_does_not_change_digest() -> None:
    demos = tuple(Demonstration(input=i, output=i) for i in range(3))
    a = TaskPackage("identity", demos, (4,), OutputSchema(kind="integer"), {"task_name": "alpha"})
    b = TaskPackage("identity", demos, (4,), OutputSchema(kind="integer"), {"task_name": "beta"})
    assert a.package_digest == b.package_digest
```

- [ ] **Step 2: Run the focused tests**

Run: `python -m pytest research/universal_core/tests/test_contracts.py -q`

Expected: FAIL because the contracts are absent.

- [ ] **Step 3: Implement canonical serialization and immutable dataclasses**

Use frozen dataclasses and validate demonstration count in `TaskPackage.__post_init__`. Detect hidden targets recursively when a hidden row is a mapping containing any of `target`, `answer`, `label`, or `gold`. Define statuses exactly as:

```python
class FailureStatus(str, Enum):
    SOLVED = "SOLVED"
    AMBIGUOUS_TASK = "AMBIGUOUS_TASK"
    INSUFFICIENT_DEMONSTRATIONS = "INSUFFICIENT_DEMONSTRATIONS"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    OUTPUT_SCHEMA_CONFLICT = "OUTPUT_SCHEMA_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
```

Canonical bytes must use UTF-8, sorted keys, compact separators, `ensure_ascii=False`, and a terminal newline.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/canonical.py research/universal_core/contracts.py research/universal_core/tests/test_contracts.py
git commit -m "feat: define canonical universal task contracts"
```

---

### Task 3: Normalize external benchmark packages without leaking metadata

**Files:**
- Create: `research/universal_core/normalizer.py`
- Create: `research/universal_core/tests/test_normalizer.py`

**Interfaces:**
- Consumes: contracts from Task 2.
- Produces: `normalize_task_payload(payload: Mapping[str, object]) -> TaskPackage`.
- Accepts aliases `instructions|prompt`, `demonstrations|examples`, `hidden_inputs|test_inputs`, and optional `output_schema`.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from universal_core.normalizer import normalize_task_payload


def test_normalizer_preserves_row_order_and_strips_routing_metadata() -> None:
    payload = {
        "task_name": "secret_benchmark_route",
        "instructions": "Return the records sorted by score.",
        "demonstrations": [
            {"input": [["a", 2], ["b", 1]], "output": [["b", 1], ["a", 2]]},
            {"input": [["c", 3], ["d", 0]], "output": [["d", 0], ["c", 3]]},
            {"input": [["e", 8], ["f", 4]], "output": [["f", 4], ["e", 8]]},
        ],
        "hidden_inputs": [[["x", 7], ["y", 5]]],
    }
    package = normalize_task_payload(payload)
    assert package.hidden_inputs[0][0][0] == "x"
    assert package.metadata["task_name"] == "secret_benchmark_route"


def test_normalizer_rejects_hidden_labels() -> None:
    payload = {
        "instructions": "Classify.",
        "demonstrations": [{"input": i, "output": i} for i in range(3)],
        "hidden_inputs": [{"input": 9, "label": 9}],
    }
    with pytest.raises(ValueError, match="hidden target"):
        normalize_task_payload(payload)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_normalizer.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement explicit alias resolution**

Resolve exactly one instruction field, one demonstration field, and one hidden-input field. Reject conflicting aliases. Convert demonstrations to `Demonstration(input=..., output=...)`. Preserve metadata in `TaskPackage.metadata`, but never pass metadata to induction interfaces introduced later.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_normalizer.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/normalizer.py research/universal_core/tests/test_normalizer.py
git commit -m "feat: normalize private benchmark packages"
```

---

### Task 4: Implement the typed task-specification IR

**Files:**
- Create: `research/universal_core/ir.py`
- Create: `research/universal_core/tests/test_ir.py`

**Interfaces:**
- Produces enums `ValueType`, `RelationKind`, and `Capability`.
- Produces frozen dataclasses `FieldSpec`, `RelationSpec`, `ConstraintSpec`, `TaskSpec`.
- Produces `TaskSpec.to_data() -> dict[str, object]` and `TaskSpec.digest -> str`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.ir import Capability, FieldSpec, TaskSpec, ValueType


def test_ir_serialization_is_deterministic() -> None:
    spec = TaskSpec(
        input_type=ValueType.LIST,
        output_type=ValueType.LIST,
        fields=(FieldSpec("record", ValueType.RECORD),),
        capabilities=(Capability.SORT, Capability.PROJECT),
        objective="sort records by numeric field 1 ascending",
    )
    assert spec.digest == spec.digest
    assert spec.to_data()["capabilities"] == ["PROJECT", "SORT"]


def test_ir_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate field"):
        TaskSpec(
            input_type=ValueType.RECORD,
            output_type=ValueType.STRING,
            fields=(FieldSpec("x", ValueType.INTEGER), FieldSpec("x", ValueType.STRING)),
            capabilities=(),
            objective="return x",
        )
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_ir.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement the IR**

Include these initial value types: `BOOLEAN`, `INTEGER`, `NUMBER`, `STRING`, `SYMBOL`, `ENUM`, `LIST`, `SET`, `MAP`, `RECORD`, `TABLE`, `GRAPH`, `INTERVAL`, `COORDINATE`, `UNKNOWN`.

Include these initial capabilities: `PARSE`, `EXTRACT`, `MAP`, `FILTER`, `GROUP`, `JOIN`, `PROJECT`, `SORT`, `COUNT`, `AGGREGATE`, `COMPARE`, `RANK`, `UNIFY`, `DEDUCE`, `PROPAGATE`, `SEARCH`, `BACKTRACK`, `SOLVE_CONSTRAINTS`, `TRAVERSE_GRAPH`, `COMPUTE_PATH`, `EVALUATE_EXPRESSION`, `TRANSFORM_COORDINATES`, `SIMULATE`, `CLASSIFY`, `FORMAT`.

Sort capabilities and fields during serialization but retain demonstration provenance as explicit integer tuples.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_ir.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/ir.py research/universal_core/tests/test_ir.py
git commit -m "feat: add typed universal reasoning IR"
```

---

### Task 5: Build the trusted operator registry and operator programs

**Files:**
- Create: `research/universal_core/operators.py`
- Create: `research/universal_core/programs.py`
- Create: `research/universal_core/tests/test_operators.py`

**Interfaces:**
- Produces `OperatorDefinition(name, input_types, output_type, execute, cost)`.
- Produces `OperatorRegistry.register()`, `get()`, and `execute()`.
- Produces `OperatorStep(operator: str, source: str, target: str, arguments: Mapping[str, object])`.
- Produces `OperatorProgram.run(value: object) -> object`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.operators import default_registry
from universal_core.programs import OperatorProgram, OperatorStep


def test_operator_program_sorts_records_by_field() -> None:
    program = OperatorProgram((
        OperatorStep("sort_records", "$input", "sorted", {"field": 1, "descending": False}),
        OperatorStep("return_value", "sorted", "$output", {}),
    ))
    assert program.run([["a", 3], ["b", 1]], default_registry()) == [["b", 1], ["a", 3]]


def test_registry_rejects_unknown_operator() -> None:
    with pytest.raises(KeyError, match="unknown operator"):
        default_registry().execute("benchmark_specific_route", 1, {})
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_operators.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement deterministic operators**

Register these V1 primitives with explicit argument validation: `identity`, `sort_values`, `sort_records`, `reverse`, `count`, `sum_numbers`, `min_value`, `max_value`, `filter_equals`, `filter_compare`, `project_field`, `group_by`, `rank_records`, `contains_token`, `all_true`, `any_true`, `graph_reachable`, `shortest_path_length`, `format_scalar`, and `return_value`.

Operators receive only serialized values and validated arguments. They cannot access metadata, filesystem paths, environment variables, or global mutable state.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_operators.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/operators.py research/universal_core/programs.py research/universal_core/tests/test_operators.py
git commit -m "feat: execute trusted operator programs"
```

---

### Task 6: Add benchmark-agnostic task induction and proposal backends

**Files:**
- Create: `research/universal_core/induction.py`
- Create: `research/universal_core/tests/test_induction.py`

**Interfaces:**
- Consumes: `TaskPackage`, `TaskSpec`, and `OperatorProgram`.
- Produces `CandidateProposal(spec: TaskSpec, program_data: Mapping[str, object], source: str, confidence: float)`.
- Produces protocol `ProposalBackend.propose(instructions: str, demonstrations: tuple[Demonstration, ...], output_schema: OutputSchema) -> tuple[CandidateProposal, ...]`.
- Produces `HeuristicProposalBackend` and `JsonProposalBackend(complete: Callable[[str], str])`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.induction import HeuristicProposalBackend, build_induction_view


def test_induction_view_excludes_metadata(task_package) -> None:
    view = build_induction_view(task_package)
    assert "task_name" not in view
    assert task_package.metadata["task_name"] == "randomized-name"


def test_heuristic_backend_infers_sort_records(task_package) -> None:
    proposals = HeuristicProposalBackend().propose(
        task_package.instructions,
        task_package.demonstrations,
        task_package.output_schema,
    )
    assert any(p.program_data["steps"][0]["operator"] == "sort_records" for p in proposals)


def test_json_backend_rejects_untyped_model_output() -> None:
    backend = JsonProposalBackend(lambda _: '{"program": "run arbitrary python"}')
    with pytest.raises(ValueError, match="proposal schema"):
        backend.propose("sort", task_package.demonstrations, task_package.output_schema)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_induction.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement deterministic hypothesis generation**

The heuristic backend must generate and score hypotheses for: identity, reverse, ascending/descending sort, record-field sort, count, sum, min, max, affine integer transform `a*x+b`, filter-plus-count, filter-plus-sum, field projection, rank, graph reachability, and keyword-relation classification.

Infer candidate parameters only from instructions and demonstrations. Enumerate all parameters that exactly fit demonstrations; do not select based on hidden rows.

The JSON backend prompt contains only instructions, demonstrations, output schema, the IR schema, the trusted operator catalog, and the MiniLang grammar. Parse strict JSON and reject unknown fields or operators.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_induction.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/induction.py research/universal_core/tests/test_induction.py
git commit -m "feat: infer task hypotheses from demonstrations"
```

---

### Task 7: Synthesize reusable algorithmic templates, including bounded constraints

**Files:**
- Create: `research/universal_core/templates.py`
- Create: `research/universal_core/tests/test_templates.py`

**Interfaces:**
- Produces `TemplateSynthesizer.synthesize(proposal: CandidateProposal) -> CandidateSolver`.
- Produces `CandidateSolver(candidate_id, spec, program, trust_level, description_length)`.
- Supports operator programs and a Z3-backed finite-ordering template selected by inferred relations, never by task name.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.templates import synthesize_ordering_solver


def test_ordering_template_solves_unseen_entity_names() -> None:
    solver = synthesize_ordering_solver(
        entities=("mira", "noah", "orion"),
        before=(("mira", "orion"), ("noah", "orion")),
        adjacent=(("mira", "noah"),),
    )
    assert solver.run({"query": "last"}) == "orion"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_templates.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement template synthesis**

Compile operator proposal JSON into `OperatorProgram`. Add a bounded ordering template using `z3.Int` positions, `Distinct`, before/after inequalities, adjacency absolute differences, and deterministic lexicographic tie-breaking. Add graph reachability and finite-state simulation templates behind the same `CandidateSolver.run(row)` interface.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_templates.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/templates.py research/universal_core/tests/test_templates.py
git commit -m "feat: synthesize reusable solver templates"
```

---

### Task 8: Implement the constrained MiniLang generated-code fallback

**Files:**
- Create: `research/universal_core/minilang.py`
- Create: `research/universal_core/tests/test_minilang.py`
- Create: `research/universal_core/tests/test_security.py`

**Interfaces:**
- Produces `MiniLangProgram.from_data(data: Mapping[str, object]) -> MiniLangProgram`.
- Produces `MiniLangProgram.run(input_value: object, limits: ExecutionLimits) -> object`.
- Produces `ExecutionLimits(max_steps=10_000, max_loop_items=1_000, max_output_bytes=1_000_000, max_depth=64)`.

- [ ] **Step 1: Write failing functional and security tests**

```python
from universal_core.minilang import ExecutionLimits, MiniLangProgram, MiniLangValidationError


def test_minilang_computes_weighted_sum() -> None:
    program = MiniLangProgram.from_data({
        "version": 1,
        "body": [
            {"op": "let", "name": "total", "value": {"literal": 0}},
            {"op": "for_each", "item": "row", "in": {"var": "$input"}, "body": [
                {"op": "set", "name": "total", "value": {
                    "call": "add",
                    "args": [{"var": "total"}, {"call": "multiply", "args": [
                        {"index": [{"var": "row"}, 0]}, {"index": [{"var": "row"}, 1]}
                    ]}],
                }},
            ]},
            {"op": "return", "value": {"var": "total"}},
        ],
    })
    assert program.run([[2, 3], [4, 5]], ExecutionLimits()) == 26


def test_minilang_rejects_host_access() -> None:
    with pytest.raises(MiniLangValidationError):
        MiniLangProgram.from_data({"version": 1, "body": [{"op": "import", "name": "os"}]})


def test_minilang_enforces_step_budget() -> None:
    program = MiniLangProgram.from_data({
        "version": 1,
        "body": [{"op": "for_each", "item": "x", "in": {"var": "$input"}, "body": []},
                 {"op": "return", "value": {"literal": 0}}],
    })
    with pytest.raises(RuntimeError, match="step budget"):
        program.run(list(range(100)), ExecutionLimits(max_steps=10))
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_minilang.py research/universal_core/tests/test_security.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement a closed interpreter**

Support statements `let`, `set`, `if`, `for_each`, and `return`. Support expressions `literal`, `var`, `index`, and calls to an explicit pure-function table containing `add`, `subtract`, `multiply`, `divide`, `mod`, `equal`, `less`, `less_equal`, `greater`, `greater_equal`, `and`, `or`, `not`, `length`, `contains`, `lower`, `split`, `join`, `sorted`, and `unique`.

Reject every unknown key, statement, function, and variable. Never call `eval`, `exec`, `compile`, `__import__`, reflection, filesystem, environment, sockets, threads, or subprocesses. Count each statement and expression evaluation against the step budget. Measure serialized output bytes before returning.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_minilang.py research/universal_core/tests/test_security.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/minilang.py research/universal_core/tests/test_minilang.py research/universal_core/tests/test_security.py
git commit -m "feat: add constrained generated-code fallback"
```

---

### Task 9: Build layered verification and counterexample search

**Files:**
- Create: `research/universal_core/verification.py`
- Create: `research/universal_core/tests/test_verification.py`

**Interfaces:**
- Produces `VerificationCheck(name, passed, evidence, failure)`.
- Produces `VerificationReport(candidate_id, checks, demonstration_accuracy, deterministic, accepted)`.
- Produces `verify_candidate(candidate: CandidateSolver, package: TaskPackage, candidate_factory: Callable | None = None) -> VerificationReport`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.verification import verify_candidate


def test_memorizing_candidate_fails_renaming_check(memorizor_candidate, affine_package) -> None:
    report = verify_candidate(memorizor_candidate, affine_package)
    assert report.accepted is False
    assert any(c.name == "entity_renaming" and not c.passed for c in report.checks)


def test_general_affine_candidate_passes_replay_and_fresh_values(affine_candidate, affine_package) -> None:
    report = verify_candidate(affine_candidate, affine_package)
    assert report.demonstration_accuracy == 1.0
    assert report.deterministic is True
    assert report.accepted is True
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_verification.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement verification checks**

Run these checks when applicable and record explicit skipped evidence when not applicable:

1. exact demonstration replay;
2. deterministic double execution;
3. output-schema validation;
4. leave-one-demonstration-out re-induction for at least four demonstrations;
5. demonstration reordering invariance;
6. entity/value alpha-renaming invariance;
7. row-order invariance for order-insensitive task specifications;
8. candidate mutation tests by altering comparison direction, aggregation, or sort direction;
9. differential agreement among independent accepted candidates;
10. bounded counterexample generation for affine, sort, filter, graph, and ordering families.

A candidate cannot be accepted unless demonstration replay, determinism, schema, and at least two nontrivial checks pass. Any executed nontrivial check failure rejects the candidate.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_verification.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/verification.py research/universal_core/tests/test_verification.py
git commit -m "feat: verify synthesized solvers against counterexamples"
```

---

### Task 10: Select candidates deterministically and expose typed abstention

**Files:**
- Create: `research/universal_core/selection.py`
- Create: `research/universal_core/tests/test_selection.py`

**Interfaces:**
- Produces `SelectionResult(status: FailureStatus, candidate: CandidateSolver | None, reason: str, ranked_ids: tuple[str, ...])`.
- Produces `select_candidate(candidates: Sequence[tuple[CandidateSolver, VerificationReport]]) -> SelectionResult`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.contracts import FailureStatus
from universal_core.selection import select_candidate


def test_selector_prefers_trusted_shorter_verified_program(verified_operator_candidate, verified_minilang_candidate) -> None:
    result = select_candidate([verified_minilang_candidate, verified_operator_candidate])
    assert result.status is FailureStatus.SOLVED
    assert result.candidate.trust_level == "trusted_operator"


def test_selector_abstains_when_candidates_disagree_without_separation(disagreeing_candidates) -> None:
    result = select_candidate(disagreeing_candidates)
    assert result.status is FailureStatus.AMBIGUOUS_TASK
    assert result.candidate is None
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_selection.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement ranking**

Sort accepted candidates by: verification pass count descending, trust level (`trusted_operator` before `template` before `minilang`), demonstration accuracy descending, description length ascending, measured runtime ascending, candidate ID ascending. If top candidates remain verification-equivalent but disagree on generated counterexamples, return `AMBIGUOUS_TASK`. Map empty proposals to `UNSUPPORTED_OPERATION`, insufficient evidence to `INSUFFICIENT_DEMONSTRATIONS`, and all rejected candidates to `VERIFICATION_FAILED`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_selection.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/selection.py research/universal_core/tests/test_selection.py
git commit -m "feat: select verified solvers with explicit abstention"
```

---

### Task 11: Freeze solvers and preserve immutable first attempts

**Files:**
- Create: `research/universal_core/sealing.py`
- Create: `research/universal_core/tests/test_sealing.py`

**Interfaces:**
- Produces `FreezeManifest` with package, spec, solver, verification, runtime, dependency, seed, and limit digests.
- Produces `freeze_solver(...) -> FreezeManifest`.
- Produces `write_first_attempt(output_root: Path, manifest: FreezeManifest, predictions: Sequence[PredictionRow]) -> Path`.
- Produces `verify_attempt(attempt_dir: Path) -> None`.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.sealing import AttemptExistsError, verify_attempt, write_first_attempt


def test_first_attempt_cannot_be_overwritten(tmp_path, manifest, predictions) -> None:
    write_first_attempt(tmp_path, manifest, predictions)
    with pytest.raises(AttemptExistsError):
        write_first_attempt(tmp_path, manifest, predictions)


def test_attempt_verification_detects_mutation(tmp_path, manifest, predictions) -> None:
    attempt = write_first_attempt(tmp_path, manifest, predictions)
    (attempt / "predictions.json").write_text("{}\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_attempt(attempt)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_sealing.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement atomic sealing**

Serialize the manifest and predictions canonically. Create `attempts/attempt-0001` with `mkdir(exist_ok=False)`. Write temporary files, `fsync`, rename atomically, and emit `SHA256.json` covering every file except itself. Never derive answers from digests. Revisions increment the attempt number and include `supersedes_attempt`, while attempt 0001 remains byte-identical.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_sealing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/sealing.py research/universal_core/tests/test_sealing.py
git commit -m "feat: seal immutable universal-core attempts"
```

---

### Task 12: Assemble the end-to-end runner and CLI

**Files:**
- Create: `research/universal_core/runner.py`
- Create: `research/universal_core/cli.py`
- Create: `research/universal_core/tests/test_runner.py`
- Create: `research/universal_core/tests/fixtures/sort_records.json`

**Interfaces:**
- Produces `UniversalCoreRunner.run(package: TaskPackage, output_root: Path) -> AttemptResult`.
- Produces CLI: `python -m universal_core.cli run --task task.json --output artifacts/run-name`.

- [ ] **Step 1: Write the failing end-to-end test**

```python
from universal_core.runner import UniversalCoreRunner


def test_runner_induces_freezes_and_executes_unseen_sort_rows(sort_package, tmp_path) -> None:
    result = UniversalCoreRunner.default().run(sort_package, tmp_path)
    assert result.status.value == "SOLVED"
    assert result.predictions[0].prediction == [["y", 5], ["x", 7]]
    assert len(result.solver_digest) == 64
    assert (tmp_path / "attempts" / "attempt-0001" / "SHA256.json").exists()
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_runner.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement the pipeline**

The runner executes exactly this sequence:

```text
normalize -> build induction view -> generate proposals -> synthesize candidates
-> verify every candidate -> select one -> freeze -> execute all hidden rows
-> validate outputs -> seal ordered predictions -> return AttemptResult
```

Do not expose `TaskPackage.metadata` to proposal backends, candidate solvers, verification, or hidden execution. Catch deterministic errors and map them to the required statuses. Record per-row runtime, confidence, status, and error text. The CLI loads JSON, prints a compact summary to stdout, and returns nonzero only for malformed input or integrity failure; scientific abstentions still produce a sealed result package.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_runner.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/runner.py research/universal_core/cli.py research/universal_core/tests/test_runner.py research/universal_core/tests/fixtures/sort_records.json
git commit -m "feat: run sealed private-benchmark inference"
```

---

### Task 13: Add fresh-instance, anti-cheating, and unseen-hash evaluation harnesses

**Files:**
- Create: `research/universal_core/tests/generators.py`
- Create: `research/universal_core/tests/test_fresh_instances.py`
- Create: `research/universal_core/tests/test_anti_cheating.py`
- Create: `research/universal_core/tests/fixtures/affine_numbers.json`
- Create: `research/universal_core/tests/fixtures/keyword_relation.json`

**Interfaces:**
- Produces deterministic generators for affine transformation, record sorting, filter/count, graph reachability, finite ordering, and lightweight keyword-relation classification.
- Each generator returns demonstrations, hidden rows, targets kept only in the test harness, and a seed manifest.

- [ ] **Step 1: Write failing invariance tests**

```python
@pytest.mark.parametrize("seed", range(20))
def test_fresh_affine_instances_generalize(seed, tmp_path) -> None:
    package, targets = generate_affine_package(seed=seed, demonstration_count=5, hidden_count=25)
    result = UniversalCoreRunner.default().run(package, tmp_path / str(seed))
    assert [row.prediction for row in result.predictions] == targets


def test_randomized_task_names_and_unseen_hashes_do_not_change_predictions(tmp_path) -> None:
    a, targets = generate_sort_package(seed=11, task_name="alpha")
    b, _ = generate_sort_package(seed=11, task_name="completely-different-private-name")
    ra = UniversalCoreRunner.default().run(a, tmp_path / "a")
    rb = UniversalCoreRunner.default().run(b, tmp_path / "b")
    assert [x.prediction for x in ra.predictions] == targets
    assert [x.prediction for x in rb.predictions] == targets
    assert ra.solver_digest == rb.solver_digest
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_fresh_instances.py research/universal_core/tests/test_anti_cheating.py -q`

Expected: one or more generated families fail before tuning.

- [ ] **Step 3: Implement generators independently from solver code**

Place all target generation in `tests/generators.py`; production modules must not import it. Generate entity names, values, ordering, row counts, and instruction paraphrases from seeded `random.Random`. Hidden inputs must have hashes absent from every demonstration. Add tests for demonstration counts 3, 5, 10, and 20.

Set the V1 release gates before tuning failures:

- exact structured fresh-instance accuracy: at least 95% across 1,000 generated hidden rows;
- lightweight semantic fresh-instance accuracy: at least 80% across 300 generated hidden rows;
- total coverage: at least 90%;
- deterministic replay: 100%;
- task-name, metadata, row-order, unseen-hash, and entity-renaming invariance: 100%;
- security-policy violations: zero;
- archive-regression failures: zero.

- [ ] **Step 4: Tune only reusable induction, templates, operators, or verification**

Do not add row hashes, test seeds, generated targets, fixture-specific identifiers, or task-name branches. Every improvement must pass the randomized-name test before commit.

- [ ] **Step 5: Run the full generated suite**

Run: `python -m pytest research/universal_core/tests/test_fresh_instances.py research/universal_core/tests/test_anti_cheating.py -q`

Expected: all release gates pass.

- [ ] **Step 6: Commit**

```bash
git add research/universal_core/tests/generators.py research/universal_core/tests/test_fresh_instances.py research/universal_core/tests/test_anti_cheating.py research/universal_core/tests/fixtures
git commit -m "test: validate fresh-instance universal reasoning"
```

---

### Task 14: Compute evaluation metrics and a complete audit package

**Files:**
- Create: `research/universal_core/metrics.py`
- Create: `research/universal_core/tests/test_metrics.py`

**Interfaces:**
- Produces `EvaluationMetrics` and `compute_metrics(rows, targets, induction_status, verification_status, resource_usage)`.
- Targets are passed only after predictions are sealed.

- [ ] **Step 1: Write failing tests**

```python
from universal_core.metrics import compute_metrics


def test_metrics_report_accuracy_and_coverage_separately() -> None:
    metrics = compute_metrics(
        predictions=("a", None, "c"),
        targets=("a", "b", "x"),
        statuses=("SOLVED", "LOW_CONFIDENCE", "SOLVED"),
    )
    assert metrics.raw_accuracy == pytest.approx(1 / 3)
    assert metrics.coverage == pytest.approx(2 / 3)
    assert metrics.attempted_accuracy == pytest.approx(1 / 2)
    assert metrics.coverage_adjusted_accuracy == pytest.approx(1 / 3)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest research/universal_core/tests/test_metrics.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement metrics**

Treat abstentions as incorrect for raw and coverage-adjusted accuracy. Include first-attempt ID, task-family and operation-family breakdowns, induction success, verification pass, deterministic replay, total runtime, peak recorded memory, synthesis candidate count, and solver trust level. Emit canonical `evaluation.json` beside the sealed attempt without altering any first-attempt file.

- [ ] **Step 4: Run tests**

Run: `python -m pytest research/universal_core/tests/test_metrics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/universal_core/metrics.py research/universal_core/tests/test_metrics.py
git commit -m "feat: report universal-core evaluation metrics"
```

---

### Task 15: Add CI reproduction, archive regression, and the V1 baseline checkpoint

**Files:**
- Create: `.github/workflows/universal-core-v1.yml`
- Create: `research/universal_core/checkpoints/2026-07-29/UNIVERSAL_CORE_V1_BASELINE.md`

**Interfaces:**
- CI uploads artifact `universal-core-v1-evidence` containing test reports, generated-suite metrics, archive verification, and a sealed sample attempt.

- [ ] **Step 1: Add the workflow with exact gates**

```yaml
name: Universal Core V1

on:
  pull_request:
    paths:
      - 'research/universal_core/**'
      - 'docs/superpowers/specs/2026-07-29-universal-core-v1-design.md'
      - 'docs/superpowers/plans/2026-07-29-universal-core-v1.md'
      - '.github/workflows/universal-core-v1.yml'
  push:
    branches: [universal-core-v1]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: git fetch origin archive/universal-bbeh-dual-track-4520-2026-07-28
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install --quiet pytest z3-solver
      - run: PYTHONPATH=research python -m pytest research/universal_core/tests -q
      - run: PYTHONPATH=research python -m universal_core.archive_guard
      - run: PYTHONPATH=research python -m universal_core.cli run --task research/universal_core/tests/fixtures/sort_records.json --output artifacts/sample
      - uses: actions/upload-artifact@v4
        with:
          name: universal-core-v1-evidence
          path: artifacts/**
          if-no-files-found: error
```

- [ ] **Step 2: Run the complete suite locally**

Run: `PYTHONPATH=research python -m pytest research/universal_core/tests -q`

Expected: all tests pass.

- [ ] **Step 3: Run archive verification**

Run: `PYTHONPATH=research python -m universal_core.archive_guard`

Expected: JSON reports the exact archive commit, matching archive branch, and zero deleted protected paths.

- [ ] **Step 4: Run a sealed sample attempt twice**

```bash
rm -rf /tmp/universal-core-v1-sample-a /tmp/universal-core-v1-sample-b
PYTHONPATH=research python -m universal_core.cli run \
  --task research/universal_core/tests/fixtures/sort_records.json \
  --output /tmp/universal-core-v1-sample-a
PYTHONPATH=research python -m universal_core.cli run \
  --task research/universal_core/tests/fixtures/sort_records.json \
  --output /tmp/universal-core-v1-sample-b
diff -ru /tmp/universal-core-v1-sample-a/attempts/attempt-0001 \
         /tmp/universal-core-v1-sample-b/attempts/attempt-0001
```

Expected: no diff.

- [ ] **Step 5: Write the baseline checkpoint**

Record the implementation commit, Python version, dependency versions, exact test counts, generated hidden-row counts, release-gate metrics, archive verification output, sample solver digest, sample prediction digest, CI run ID, artifact ID, artifact digest, known unsupported operations, and the scientific claim boundary. Do not describe public-corpus fit as unseen generalization.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/universal-core-v1.yml research/universal_core/checkpoints/2026-07-29/UNIVERSAL_CORE_V1_BASELINE.md
git commit -m "ci: seal Universal Core V1 baseline"
```

---

## Final Verification Checklist

- [ ] `git diff --diff-filter=D a0c099a41c85f267ca6323235a019b2052107873...HEAD -- research/universal_validation .github/workflows/universal-semantic-dual-track-v1.yml` prints nothing.
- [ ] `PYTHONPATH=research python -m pytest research/universal_core/tests -q` passes.
- [ ] Archive branch resolves to `a0c099a41c85f267ca6323235a019b2052107873`.
- [ ] No production source contains `eval(`, `exec(`, benchmark task names, target-ledger imports, or row-hash answer lookup.
- [ ] Randomized task names, inert metadata changes, row reordering, entity renaming, and unseen hashes do not alter equivalent predictions.
- [ ] MiniLang security tests show zero host-capability access.
- [ ] Solver and prediction seals verify after an independent replay.
- [ ] First-attempt files reject overwrite.
- [ ] Generated exact, semantic, coverage, replay, anti-cheating, security, and archive gates meet the fixed thresholds.
- [ ] CI uploads a complete evidence artifact and the checkpoint records its digest.
- [ ] Open a draft PR from `universal-core-v1` immediately after the first implementation commit; do not merge it during implementation.
