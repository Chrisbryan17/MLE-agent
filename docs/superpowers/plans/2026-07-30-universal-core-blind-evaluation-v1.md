# Universal Core Blind Evaluation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an additive commit-predict-reveal protocol that lets an external evaluator commit to private targets and scoring rules, receive a sealed submission from frozen Universal Core V1, reveal the private bundle, and reproduce the score offline.

**Architecture:** Add `universal_core.blind_eval` around the unchanged reasoning engine. Canonical protocol objects bind the public challenge, private reveal, scoring policy, frozen core, submission, score report, and evidence package with SHA-256. Validation fails closed on leakage, ordering changes, identity changes, premature reveal, overwrite attempts, or tampering.

**Tech Stack:** Python 3.12; standard library at runtime; existing `universal_core` canonicalization, contracts, runner, sealing, and archive guard; pytest 9.0.2; z3-solver 4.15.3.0 for the unchanged core test environment; GitHub Actions.

## Global Constraints

- Frozen core: `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`.
- Preserved BBEH archive: `archive/universal-bbeh-dual-track-4520-2026-07-28` at `a0c099a41c85f267ca6323235a019b2052107873`.
- Protocol version: `universal-core-blind-eval-v1`.
- Production changes are additive under `research/universal_core/blind_eval/`; existing top-level `research/universal_core/*.py` files are immutable.
- Canonical JSON is UTF-8, sorted keys, compact separators, finite numbers only, and one terminal newline.
- Digests are lowercase SHA-256 hexadecimal strings. Nonces contain at least 32 random bytes.
- Public tasks contain opaque IDs, instructions, 3–20 demonstrations, hidden inputs, output schema, and optional resource limits—never targets, private family IDs, levels, generator source, evaluator notes, or routing hints.
- `PublicChallengeSuite.binding_data()` excludes `commitment_digest` to avoid self-reference.
- `PrivateReveal.binding_data()` excludes `commitment_digest` and `reveal_digest`; the final serialized reveal remains covered by the evidence manifest.
- Other self-digested objects exclude only their own digest field.
- Scoring is blocked unless challenge, commitment, submission, reveal, task order, row order, core identity, timestamps, and manifests verify.
- Repository fixtures validate protocol mechanics only. The 12-family, 600-row scientific suite remains outside this repository.
- No minimum accuracy is imposed on the first real blind evaluation.
- Each task uses red-green TDD and ends with one atomic commit.

## File Structure

```text
research/universal_core/blind_eval/
  __init__.py
  constants.py
  errors.py
  contracts.py
  commitment.py
  challenge.py
  core_identity.py
  submission.py
  equivalence.py
  reveal.py
  statistics.py
  scoring.py
  evidence.py
  cli.py
  tests/
  checkpoints/2026-07-30/BLIND_EVAL_PROTOCOL_V1.md
.github/workflows/universal-core-blind-eval-v1.yml
```

---

### Task 1: Canonical Protocol Contracts

**Files:**
- Create: `research/universal_core/blind_eval/__init__.py`
- Create: `research/universal_core/blind_eval/constants.py`
- Create: `research/universal_core/blind_eval/errors.py`
- Create: `research/universal_core/blind_eval/contracts.py`
- Create: `research/universal_core/blind_eval/tests/__init__.py`
- Create: `research/universal_core/blind_eval/tests/test_contracts.py`

**Interfaces:**
- Constants: `PROTOCOL_VERSION`, `FROZEN_CORE_COMMIT`, `ARCHIVE_BRANCH`, `ARCHIVE_COMMIT`, `MIN_NONCE_BYTES`, `FORBIDDEN_PUBLIC_KEYS`.
- Errors: `ProtocolError`, `CommitmentError`, `SubmissionError`, `ScoringError`, `AuditError`.
- Enums: `GeneralizationLevel`, `RowOutcome`, `EquivalenceKind`.
- Dataclasses: `EquivalenceRule`, `ScoringPolicy`, `PublicTask`, `PublicChallengeSuite`, `ChallengeCommitment`, `CoreIdentity`, `TaskSubmission`, `SubmissionEnvelope`, `IndependenceAttestation`, `TaskReveal`, `PrivateReveal`.
- Every contract has strict `from_data()` and deterministic `to_data()`; self-digested objects also have `binding_data()`.

- [ ] **Step 1: Write failing contract tests**

```python
import pytest

from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT, PROTOCOL_VERSION
from universal_core.blind_eval.contracts import GeneralizationLevel, PublicChallengeSuite


def test_protocol_identity_is_pinned() -> None:
    assert PROTOCOL_VERSION == "universal-core-blind-eval-v1"
    assert FROZEN_CORE_COMMIT == "89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9"
    assert [level.value for level in GeneralizationLevel] == [1, 2, 3, 4]


def test_public_binding_excludes_commitment_link(public_suite: PublicChallengeSuite) -> None:
    assert "commitment_digest" not in public_suite.binding_data()
    assert "commitment_digest" in public_suite.to_data()


def test_unknown_fields_fail_closed(public_suite: PublicChallengeSuite) -> None:
    with pytest.raises(ValueError, match="unknown PublicChallengeSuite fields"):
        PublicChallengeSuite.from_data(public_suite.to_data() | {"private_family": "x"})
```

- [ ] **Step 2: Verify the red state**

```bash
PYTHONPATH=research python -m pytest research/universal_core/blind_eval/tests/test_contracts.py -q
```

Expected: import failure because the package does not exist.

- [ ] **Step 3: Implement pinned constants and error hierarchy**

```python
PROTOCOL_VERSION = "universal-core-blind-eval-v1"
FROZEN_CORE_COMMIT = "89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9"
ARCHIVE_BRANCH = "archive/universal-bbeh-dual-track-4520-2026-07-28"
ARCHIVE_COMMIT = "a0c099a41c85f267ca6323235a019b2052107873"
MIN_NONCE_BYTES = 32
FORBIDDEN_PUBLIC_KEYS = frozenset({
    "target", "targets", "answer", "answers", "label", "labels", "gold",
    "family", "family_id", "task_family", "generalization_level",
    "generator", "generator_source", "private_notes", "routing_hint",
})

class ProtocolError(ValueError):
    pass
class CommitmentError(ProtocolError):
    pass
class SubmissionError(ProtocolError):
    pass
class ScoringError(ProtocolError):
    pass
class AuditError(ProtocolError):
    pass
```

- [ ] **Step 4: Implement strict validation helpers**

Require exact field sets, lowercase 64-character SHA-256 values, opaque IDs matching `^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$`, finite numeric trees, unique ordered task IDs, contiguous row indexes, and valid UTC timestamps. Reject recursive forbidden public keys.

- [ ] **Step 5: Implement enums and protocol dataclasses**

`GeneralizationLevel` is an `IntEnum` with values 1–4. `RowOutcome` includes `CORRECT`, `INCORRECT`, `ABSTAINED`, `EXECUTION_FAILURE`, `OUTPUT_SCHEMA_CONFLICT`, `INVALID_SUBMISSION`, and `EVALUATOR_DEFECT_EXCLUSION`. `EquivalenceKind` includes `EXACT`, `CASEFOLD_STRING`, `UNORDERED_SEQUENCE`, `RATIONAL_NUMBER`, `NUMERIC_TOLERANCE`, and `GRAPH_EDGE_SET`.

`PublicTask.to_task_package()` converts only public fields into the existing `TaskPackage`. `PublicChallengeSuite.binding_data()` excludes only `commitment_digest`. `PrivateReveal.binding_data()` excludes `commitment_digest` and `reveal_digest`. Digest properties use `sha256_hex(canonical_json_bytes(...))`.

- [ ] **Step 6: Add negative tests**

Cover non-finite numbers, duplicate IDs, malformed digests, invalid levels, fewer than 3 or more than 20 demonstrations, empty hidden inputs, negative tolerances, noncontiguous predictions, and forbidden nested keys.

- [ ] **Step 7: Run tests and commit**

```bash
PYTHONPATH=research python -m pytest research/universal_core/blind_eval/tests/test_contracts.py -q
git add research/universal_core/blind_eval
git commit -m "feat: define blind evaluation contracts"
```

---

### Task 2: Commitment Construction and Public/Private Separation

**Files:**
- Create: `research/universal_core/blind_eval/commitment.py`
- Create: `research/universal_core/blind_eval/challenge.py`
- Create: `research/universal_core/blind_eval/tests/test_commitment.py`
- Create: `research/universal_core/blind_eval/tests/test_challenge.py`

**Interfaces:**
- `generate_nonce(random_bytes: Callable[[int], bytes] = secrets.token_bytes) -> str`
- `build_commitment(public_suite, private_reveal, scoring_policy, *, created_at) -> ChallengeCommitment`
- `verify_commitment(commitment, public_suite, private_reveal) -> None`
- `scan_public_payload(value, path="$") -> None`
- `prepare_committed_bundle(public_draft, reveal_draft, *, nonce, created_at) -> tuple[ChallengeCommitment, PublicChallengeSuite, PrivateReveal]`

- [ ] **Step 1: Write failing substitution and leakage tests**

```python
def test_target_change_breaks_commitment(committed_bundle) -> None:
    commitment, public, reveal = committed_bundle
    changed = replace(reveal, task_reveals=(replace(reveal.task_reveals[0], targets=(999,)),))
    with pytest.raises(CommitmentError, match="private reveal digest mismatch"):
        verify_commitment(commitment, public, changed)


def test_family_metadata_is_rejected(public_payload) -> None:
    public_payload["tasks"][0]["metadata"] = {"family_id": "secret"}
    with pytest.raises(ProtocolError, match="forbidden public key"):
        scan_public_payload(public_payload)
```

- [ ] **Step 2: Verify red state**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_commitment.py \
  research/universal_core/blind_eval/tests/test_challenge.py -q
```

- [ ] **Step 3: Implement nonce and binding digests**

Nonce is lowercase hexadecimal encoding of at least 32 bytes. Compute `public_challenge_digest` from `public_suite.binding_data()`, `private_reveal_digest` from `private_reveal.binding_data()`, and `scoring_policy_digest` from the policy’s canonical data. Commitment digest excludes only its own digest field.

- [ ] **Step 4: Implement bundle preparation order**

Validate drafts, inject the nonce into the private reveal, compute challenge/reveal/policy digests, build the commitment, then inject the final commitment digest into the public suite and reveal. Reverify every digest before returning.

- [ ] **Step 5: Add tamper tests**

Cover changed nonce, changed scoring policy, added/removed/reordered task, changed frozen core, hidden target injection, generator-source leakage, and commitment self-link mutation.

- [ ] **Step 6: Run and commit**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_commitment.py \
  research/universal_core/blind_eval/tests/test_challenge.py -q
git add research/universal_core/blind_eval
git commit -m "feat: bind blind challenge and reveal"
```

---

### Task 3: Frozen-Core Identity and Sealed Submission

**Files:**
- Create: `research/universal_core/blind_eval/core_identity.py`
- Create: `research/universal_core/blind_eval/submission.py`
- Create: `research/universal_core/blind_eval/tests/test_core_identity.py`
- Create: `research/universal_core/blind_eval/tests/test_submission.py`

**Interfaces:**
- `build_core_identity(repo_root: Path, commit=FROZEN_CORE_COMMIT) -> CoreIdentity`
- `verify_frozen_core(repo_root: Path, identity: CoreIdentity) -> None`
- `run_public_suite(commitment, suite, output_root, *, repo_root, runner_factory=UniversalCoreRunner.default, created_at) -> SubmissionEnvelope`
- `verify_submission(commitment, suite, submission, *, require_before_reveal: str | None = None) -> None`

- [ ] **Step 1: Write failing identity and first-attempt tests**

```python
def test_core_identity_matches_frozen_tree(repo_root) -> None:
    identity = build_core_identity(repo_root)
    assert identity.commit == FROZEN_CORE_COMMIT
    assert len(identity.source_digest) == 64


def test_submission_is_first_attempt_only(committed_public, tmp_path, repo_root) -> None:
    commitment, suite = committed_public
    run_public_suite(commitment, suite, tmp_path, repo_root=repo_root, created_at=FIXED_TIME)
    with pytest.raises(FileExistsError, match="first attempt"):
        run_public_suite(commitment, suite, tmp_path, repo_root=repo_root, created_at=FIXED_TIME)
```

- [ ] **Step 2: Verify red state**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_core_identity.py \
  research/universal_core/blind_eval/tests/test_submission.py -q
```

- [ ] **Step 3: Implement frozen source identity**

List frozen production files with `git ls-tree -r --name-only <commit> -- research/universal_core`, excluding `tests/`, `blind_eval/`, checkpoints, and generated caches. Hash each `git show <commit>:<path>` byte sequence and bind the ordered path/digest map into `source_digest`. Verify current bytes match the frozen map before submission.

- [ ] **Step 4: Implement suite execution**

For each public task in declared order: convert to `TaskPackage`, create `tasks/<task_id>/`, run the existing frozen `UniversalCoreRunner`, verify `attempts/attempt-0001`, read sealed prediction and solver digests, and construct `TaskSubmission` without modifying the nested attempt.

- [ ] **Step 5: Seal submission atomically**

Write `CORE_IDENTITY.json`, `SUBMISSION.json`, `TASK_MANIFEST.json`, and each copied attempt through exclusive atomic writes. Submission digest excludes only `submission_digest`. Reject duplicate task IDs, altered row order, mismatched package digests, altered core identity, and preexisting output.

- [ ] **Step 6: Run frozen regression and commit**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_core_identity.py \
  research/universal_core/blind_eval/tests/test_submission.py -q
PYTHONPATH=research python -m pytest research/universal_core/tests -q
git add research/universal_core/blind_eval
git commit -m "feat: seal frozen core submissions"
```

---

### Task 4: Reveal Verification and Equivalence Rules

**Files:**
- Create: `research/universal_core/blind_eval/equivalence.py`
- Create: `research/universal_core/blind_eval/reveal.py`
- Create: `research/universal_core/blind_eval/tests/test_equivalence.py`
- Create: `research/universal_core/blind_eval/tests/test_reveal.py`

**Interfaces:**
- `answers_equivalent(prediction: Any, target: Any, rule: EquivalenceRule) -> bool`
- `verify_reveal(commitment, suite, submission, reveal) -> None`
- `validate_independence_attestation(attestation) -> None`

- [ ] **Step 1: Write failing equivalence tests**

```python
@pytest.mark.parametrize(("rule", "left", "right"), [
    (EquivalenceRule(EquivalenceKind.EXACT), {"x": 1}, {"x": 1}),
    (EquivalenceRule(EquivalenceKind.CASEFOLD_STRING), "Alert", "alert"),
    (EquivalenceRule(EquivalenceKind.UNORDERED_SEQUENCE), [3, 1, 2], [2, 3, 1]),
    (EquivalenceRule(EquivalenceKind.RATIONAL_NUMBER), "2/4", "1/2"),
    (EquivalenceRule(EquivalenceKind.NUMERIC_TOLERANCE, absolute_tolerance=1e-6), 1.0, 1.0000005),
    (EquivalenceRule(EquivalenceKind.GRAPH_EDGE_SET), [["a", "b"], ["b", "c"]], [["b", "c"], ["a", "b"]]),
])
def test_precommitted_equivalence(rule, left, right) -> None:
    assert answers_equivalent(left, right, rule)
```

- [ ] **Step 2: Write failing reveal tests**

Require exact task ordering, exact target row counts, commitment link, nonce, policy digest, reveal digest, construction provenance, and a valid independence attestation. A reveal timestamp must not precede the submission timestamp.

- [ ] **Step 3: Implement deterministic normalizers**

Use canonical bytes to compare unordered items, `fractions.Fraction` for rational values, `math.isclose` with precommitted finite tolerances, and normalized directed/undirected edge sets for graph outputs. Reject unsupported values rather than guessing.

- [ ] **Step 4: Implement reveal verification**

Verify the commitment before examining correctness. Compare suite IDs, task IDs, row counts, scoring-policy digest, nonce-bound reveal digest, frozen core, and timestamps. Unexpected ambiguity is a versioned evaluator defect, never an unrecorded scoring adjustment.

- [ ] **Step 5: Run and commit**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_equivalence.py \
  research/universal_core/blind_eval/tests/test_reveal.py -q
git add research/universal_core/blind_eval
git commit -m "feat: verify reveals and answer equivalence"
```

---

### Task 5: Deterministic Scoring and Level Reporting

**Files:**
- Create: `research/universal_core/blind_eval/statistics.py`
- Create: `research/universal_core/blind_eval/scoring.py`
- Create: `research/universal_core/blind_eval/tests/test_statistics.py`
- Create: `research/universal_core/blind_eval/tests/test_scoring.py`

**Interfaces:**
- `wilson_interval(successes: int, total: int, confidence=0.95) -> tuple[float, float]`
- `score_submission(commitment, suite, submission, reveal) -> Mapping[str, Any]`
- `verify_score_report(report, commitment, suite, submission, reveal) -> None`

- [ ] **Step 1: Write failing Wilson tests**

```python
def test_wilson_interval_known_value() -> None:
    lower, upper = wilson_interval(50, 100)
    assert lower == pytest.approx(0.4038, abs=1e-4)
    assert upper == pytest.approx(0.5962, abs=1e-4)


def test_wilson_empty_population_is_zero_interval() -> None:
    assert wilson_interval(0, 0) == (0.0, 0.0)
```

- [ ] **Step 2: Write failing scoring tests**

Assert separate raw accuracy, attempted accuracy, coverage, abstention, induction/verification/execution success rates, task macro-average, Wilson intervals, per-family results, and mandatory Level 1–4 sections. Assert Level 4 first-attempt raw accuracy at observed coverage appears in `headline`.

- [ ] **Step 3: Implement row classification**

Map frozen statuses to outcomes: solved and equivalent → correct; solved and non-equivalent → incorrect; low-confidence/ambiguous/unsupported/insufficient/verification failure → abstained; execution failure and output-schema conflict retain separate outcomes. Evaluator-defect exclusions are permitted only when precommitted or covered by a versioned adjudication record.

- [ ] **Step 4: Implement aggregates**

For each task, family, and level compute total scored rows, correct, incorrect, attempted, abstained, failures, raw accuracy, attempted accuracy, coverage, abstention rate, and 95% Wilson interval. Task macro-average is the arithmetic mean of task raw accuracies. Invalid submissions return an invalid report without a valid aggregate score.

- [ ] **Step 5: Seal and verify reports**

`report_digest` excludes only itself. Bind commitment, public challenge, submission, reveal, scoring policy, first-attempt identity, and generation timestamp. Recompute the report during verification and compare canonical bytes.

- [ ] **Step 6: Run and commit**

```bash
PYTHONPATH=research python -m pytest \
  research/universal_core/blind_eval/tests/test_statistics.py \
  research/universal_core/blind_eval/tests/test_scoring.py -q
git add research/universal_core/blind_eval
git commit -m "feat: score blind submissions by level"
```

---

### Task 6: Immutable Evidence and Offline Audit

**Files:**
- Create: `research/universal_core/blind_eval/evidence.py`
- Create: `research/universal_core/blind_eval/tests/test_evidence.py`

**Interfaces:**
- `write_canonical_exclusive(path: Path, value: Any) -> None`
- `build_manifest(root: Path, *, exclude=("SHA256SUMS",)) -> Mapping[str, str]`
- `verify_manifest(root: Path, manifest) -> None`
- `build_evidence_directory(output_root, commitment, suite, submission_root, reveal, report, environment) -> Path`
- `build_deterministic_zip(evidence_root: Path, zip_path: Path) -> str`
- `audit_evidence(path: Path) -> Mapping[str, Any]`

- [ ] **Step 1: Write failing immutability and manifest tests**

```python
def test_exclusive_write_cannot_overwrite(tmp_path) -> None:
    path = tmp_path / "COMMITMENT.json"
    write_canonical_exclusive(path, {"a": 1})
    with pytest.raises(FileExistsError):
        write_canonical_exclusive(path, {"a": 2})


def test_unmanifested_file_fails(tmp_path) -> None:
    (tmp_path / "A.json").write_text("{}\n")
    manifest = build_manifest(tmp_path)
    (tmp_path / "extra.txt").write_text("x")
    with pytest.raises(AuditError, match="manifest file set mismatch"):
        verify_manifest(tmp_path, manifest)
```

- [ ] **Step 2: Implement evidence layout**

Write `COMMITMENT.json`, `PUBLIC_CHALLENGE.json`, `SUBMISSION.json`, `PRIVATE_REVEAL.json`, `SCORE_REPORT.json`, `INDEPENDENCE_ATTESTATION.json`, `ENVIRONMENT.json`, `CORE_IDENTITY.json`, `AUDIT_MANIFEST.json`, `SHA256SUMS`, and `attempts/<task-id>/...`. Copy nested attempts byte-for-byte and verify them before and after copying.

- [ ] **Step 3: Implement deterministic ZIP**

Sort paths, normalize separators, use fixed timestamp `(1980, 1, 1, 0, 0, 0)`, stable permissions, `ZIP_DEFLATED`, no extra fields, and exclusive output creation. Return the ZIP SHA-256 digest.

- [ ] **Step 4: Implement offline audit**

Audit extracted directories or ZIPs without network access. Verify top-level manifest, nested attempt manifests, commitment, reveal, submission, score recomputation, core identity, task/row order, timestamps, and ZIP path safety. Reject absolute paths and `..` traversal.

- [ ] **Step 5: Run and commit**

```bash
PYTHONPATH=research python -m pytest research/universal_core/blind_eval/tests/test_evidence.py -q
git add research/universal_core/blind_eval
git commit -m "feat: package blind evaluation evidence"
```

---

### Task 7: CLI, End-to-End Flow, and Tamper Matrix

**Files:**
- Create: `research/universal_core/blind_eval/cli.py`
- Create: `research/universal_core/blind_eval/tests/fixtures/public_challenge_draft.json`
- Create: `research/universal_core/blind_eval/tests/fixtures/private_reveal_draft.json`
- Create: `research/universal_core/blind_eval/tests/test_cli.py`
- Create: `research/universal_core/blind_eval/tests/test_end_to_end.py`
- Create: `research/universal_core/blind_eval/tests/test_tamper_matrix.py`

**Interfaces:**
- CLI commands: `commit`, `submit`, `score`, `audit`.
- Exit code `0`: valid completion; `2`: I/O, JSON, schema, or argument error; `3`: protocol, scoring-validity, or audit failure.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_commit_command_writes_three_objects(tmp_path) -> None:
    assert main([
        "commit", "--public", str(PUBLIC_DRAFT), "--private", str(REVEAL_DRAFT),
        "--output", str(tmp_path), "--created-at", FIXED_TIME,
    ]) == 0
    assert (tmp_path / "COMMITMENT.json").is_file()
    assert (tmp_path / "PUBLIC_CHALLENGE.json").is_file()
    assert (tmp_path / "PRIVATE_REVEAL.json").is_file()


def test_wrong_core_commit_is_protocol_failure(tmp_path) -> None:
    assert main([
        "submit", "--commitment", str(COMMITMENT), "--challenge", str(CHALLENGE),
        "--core-commit", "0" * 40, "--output", str(tmp_path),
        "--created-at", FIXED_TIME,
    ]) == 3
```

- [ ] **Step 2: Implement parser**

Commands:

```text
commit --public --private --output --created-at
submit --commitment --challenge --core-commit --repo-root --output --created-at
score --commitment --challenge --submission --reveal --output
audit --evidence
```

All output files use exclusive canonical writes. Errors are emitted as canonical JSON to stderr with stable error type and message.

- [ ] **Step 3: Add deterministic fixtures**

Use fixed nonce and timestamps, one exact task, one lightweight semantic task, exact scoring, and stable fake provenance hashes. Every fixture module states: `Protocol mechanics fixtures only; not independent blind-evaluation evidence.`

- [ ] **Step 4: Write full round-trip test**

Commit drafts, submit with the frozen core, reveal and score, build evidence, audit it twice, and assert byte-identical submissions, reports, manifests, and ZIP archives.

- [ ] **Step 5: Implement tamper matrix**

| Mutation | Required failure |
|---|---|
| changed target | private reveal digest mismatch |
| changed scoring policy | scoring policy digest mismatch |
| changed nonce | private reveal digest mismatch |
| reordered rows | submission row ordering mismatch |
| changed prediction | submission digest mismatch |
| changed core identity | core identity mismatch |
| hidden label injection | forbidden public key |
| family metadata leakage | forbidden public key |
| task added/removed/reordered | task ordering mismatch |
| postcommit exclusion | scoring policy digest mismatch |
| first-attempt overwrite | first attempt already exists |
| unmanifested evidence file | manifest file set mismatch |

- [ ] **Step 6: Run full local tests and commit**

```bash
PYTHONPATH=research python -m pytest research/universal_core/blind_eval/tests -q
PYTHONPATH=research python -m pytest research/universal_core/tests -q
PYTHONPATH=research python -m universal_core.archive_guard
git add research/universal_core/blind_eval
git commit -m "test: close blind evaluation protocol flow"
```

---

### Task 8: CI Evidence, Checkpoint, and Draft PR

**Files:**
- Create: `.github/workflows/universal-core-blind-eval-v1.yml`
- Create: `research/universal_core/blind_eval/tests/test_ci_contract.py`
- Create: `research/universal_core/blind_eval/checkpoints/2026-07-30/BLIND_EVAL_PROTOCOL_V1.md`

**Interfaces:**
- GitHub artifact: `universal-core-blind-eval-v1-evidence`.
- Claims-disciplined checkpoint with exact final-head evidence.

- [ ] **Step 1: Write failing CI-contract tests**

```python
def test_workflow_contains_required_guards() -> None:
    workflow = (REPO_ROOT / ".github/workflows/universal-core-blind-eval-v1.yml").read_text()
    for token in (
        "python -m pytest research/universal_core/tests",
        "python -m pytest research/universal_core/blind_eval/tests",
        "python -m universal_core.archive_guard",
        FROZEN_CORE_COMMIT,
        "universal-core-blind-eval-v1-evidence",
        "prohibited-mechanism-scan",
    ):
        assert token in workflow


def test_checkpoint_preserves_claim_boundary() -> None:
    text = CHECKPOINT.read_text().casefold()
    assert "protocol mechanics" in text
    assert "not an independent blind benchmark" in text
    assert "no scientific accuracy result" in text
```

- [ ] **Step 2: Create pinned workflow**

Use Ubuntu, Python 3.12, pytest 9.0.2, and z3-solver 4.15.3.0. The workflow:

1. fetches and verifies the archive branch and commit;
2. compares each current top-level `research/universal_core/*.py` file byte-for-byte with `git show 89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9:<path>`;
3. runs frozen-core and blind-evaluation test suites;
4. runs `universal_core.archive_guard`;
5. performs the full fixture protocol twice;
6. requires byte-identical submissions, score reports, and ZIPs;
7. runs the tamper matrix;
8. scans blind production files for dynamic execution, benchmark routes, correction ledgers, input-hash answer maps, and test-generator imports;
9. builds a top-level SHA-256 artifact manifest;
10. uploads `universal-core-blind-eval-v1-evidence` for 30 days.

- [ ] **Step 3: Create initial checkpoint**

Record protocol version, frozen identities, contracts, CLI, observed local test totals, known limits, external-evaluator instructions, and claims boundary. State that fixture scores are protocol mechanics and no independent blind accuracy result exists.

- [ ] **Step 4: Run full local verification**

```bash
python -m pip install --disable-pip-version-check --quiet pytest==9.0.2 z3-solver==4.15.3.0
PYTHONPATH=research python -m pytest research/universal_core/tests -q
PYTHONPATH=research python -m pytest research/universal_core/blind_eval/tests -q
PYTHONPATH=research python -m universal_core.archive_guard
```

Record totals only after every command exits zero.

- [ ] **Step 5: Commit CI and checkpoint**

```bash
git add .github/workflows/universal-core-blind-eval-v1.yml \
        research/universal_core/blind_eval/tests/test_ci_contract.py \
        research/universal_core/blind_eval/checkpoints/2026-07-30/BLIND_EVAL_PROTOCOL_V1.md
git commit -m "ci: seal blind evaluation protocol v1"
```

- [ ] **Step 6: Execute from an isolated implementation branch**

Create `universal-core-blind-eval-v1` from this plan commit. Open a draft PR against `universal-core-blind-eval-v1-design` immediately after Task 1’s first implementation commit. Keep it draft and do not merge.

- [ ] **Step 7: Verify exact final-head hosted evidence**

Require every workflow step to pass on the exact head; download the artifact; independently verify the ZIP digest, top-level manifest, nested attempt manifests, commitment/reveal/submission/report digests, replay identity, and recomputed score. Record exact head SHA, run ID, job ID, artifact ID, artifact digest, artifact size, test totals, and manifest counts in one evidence-only commit; rerun CI on that head; then update only PR metadata.

- [ ] **Step 8: Run non-destruction and claims audit**

```bash
git diff --name-status 89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9...HEAD
git diff --name-only --diff-filter=DM \
  89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9...HEAD -- \
  'research/universal_core/*.py' \
  research/universal_validation \
  .github/workflows/universal-semantic-dual-track-v1.yml
```

Expected: additive blind-evaluation, docs, and workflow files only; zero modified or deleted frozen production/archive files; no claim that repository fixtures are independent blind performance.

---

## Completion Checklist

- [ ] Strict canonical contracts and binding views are implemented.
- [ ] Challenge, reveal, and scoring substitution break the commitment.
- [ ] Hidden targets and private metadata fail closed.
- [ ] Frozen core production bytes match `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`.
- [ ] Submissions are ordered, sealed, immutable, and first-attempt-only.
- [ ] Reveal provenance and row counts verify before scoring.
- [ ] Every precommitted equivalence rule is deterministic.
- [ ] Reports separate raw accuracy, attempted accuracy, coverage, abstention, task macro-average, Wilson intervals, and Levels 1–4.
- [ ] Level 4 first-attempt raw accuracy at observed coverage is prominent.
- [ ] Invalid submissions receive no valid aggregate score.
- [ ] Evidence manifests and deterministic ZIP audit reproduce offline.
- [ ] CLI commit-submit-score-audit flow passes.
- [ ] Full tamper matrix fails closed.
- [ ] Frozen-core tests and archive guard remain green.
- [ ] Exact final-head CI evidence is independently verified.
- [ ] Real 12-family, 600-row scientific suite remains outside the repository.
