# Universal Core Blind Evaluation V1 Design

**Date:** 2026-07-30  
**Frozen core:** `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`  
**Design branch:** `universal-core-blind-eval-v1-design`  
**Preserved PR:** `#33`  
**Preserved BBEH archive:** `archive/universal-bbeh-dual-track-4520-2026-07-28` at `a0c099a41c85f267ca6323235a019b2052107873`

## Goal

Create an externally controlled commit-predict-reveal protocol for testing the frozen Universal Core on task families, hidden targets, and scoring logic unavailable to the solver and developers before prediction sealing.

Report four generalization levels separately:

1. unseen rows from familiar computational families;
2. unfamiliar representations of familiar computations;
3. unseen compositions of known reasoning primitives;
4. genuinely unseen rule systems or task families.

The primary scientific result is **Level 4 first-attempt raw accuracy at observed coverage**. Aggregate accuracy may not hide Level 4 failure.

## Claims boundary

A completed run may claim that the evaluator committed to targets and scoring before predictions existed, the frozen core produced immutable predictions before reveal, and the score reproduces from the committed artifacts. It does not prove unrestricted universal reasoning or guaranteed performance on arbitrary private benchmarks.

## Preservation

Blind-evaluation work is additive. It must not rewrite or delete the frozen Universal Core head, PR #33 evidence, archived BBEH state, `research/universal_validation/`, or any prior first-attempt artifact. Improvements after a blind score require a new core version and separately labeled attempt.

## Roles

**Evaluator:** creates private task definitions, generators or manual construction records, targets, scoring rules, nonce material, provenance, and reveal package; publishes a commitment before receiving predictions.

**Solver operator:** receives only the public challenge, runs the frozen core, and returns a sealed submission. No hidden targets, private generators, family labels, answer rationales, or post-generation corrections are available.

**Auditor:** independently verifies hashes, ordering, frozen-core identity, commitment integrity, reveal integrity, scoring, manifests, and replay. The strongest evaluation uses distinct evaluator and auditor parties.

## Protocol

```text
private evaluator state
  -> commitment published
  -> public challenge released
  -> frozen core induces, verifies, and freezes one solver per task
  -> predictions sealed and submission digest published
  -> evaluator reveals targets and nonce
  -> commitment verified
  -> deterministic scoring
  -> independent audit
```

Targets may not be revealed before the submission digest is externally recorded.

## Canonical contracts

All protocol objects use canonical UTF-8 JSON with sorted keys, compact separators, finite numbers only, and one terminal newline. SHA-256 is computed over canonical bytes.

### ChallengeCommitment

Contains `protocol_version`, `suite_id`, `public_challenge_digest`, `private_reveal_digest`, `scoring_policy_digest`, `frozen_core_commit`, `created_at`, and `commitment_digest`. The commitment excludes its own digest from the hashed payload. A minimum 256-bit random nonce is stored in the private reveal.

### PublicChallengeSuite

Contains `protocol_version`, `suite_id`, `commitment_digest`, `frozen_core_commit`, `tasks`, `public_scoring_specification`, and inert metadata.

Each task contains an opaque task ID, instructions, 3-20 labeled demonstrations, hidden unlabeled inputs, output schema, and optional resource limits. It contains no target, family name, generalization-level label, generator source, or routing hint. Recursive hidden keys such as `target`, `answer`, `label`, or `gold` are rejected.

### SubmissionEnvelope

Contains `protocol_version`, suite and commitment identities, public challenge digest, frozen core commit, core artifact digest, environment, ordered task submissions, timestamp, and submission digest.

Each task submission records package digest, solver digest or unresolved status, ordered predictions, prediction digest, per-row status and confidence, immutable attempt ID, verification summary, resource usage, and audit-manifest digest.

### PrivateReveal

Contains `protocol_version`, suite and commitment identities, nonce, task reveals, scoring policy, independence attestation, and reveal digest.

Each task reveal contains exact targets in row order, private family identifier, generalization level, construction method, provenance, ambiguity annotations, and precommitted equivalence rules. Its digest must match the original commitment.

## Scoring

Rows are classified as correct, incorrect, abstained, execution failure, output-schema conflict, invalid submission, or evaluator-defect exclusion.

Required metrics:

- raw accuracy over all scored rows;
- attempted-row accuracy;
- coverage and abstention rate;
- induction, verification, and execution success rates;
- deterministic replay rate;
- task macro-average;
- per-family and per-level results;
- resource usage;
- two-sided 95% Wilson intervals.

Levels 1-4 are mandatory separate sections. The headline metric is Level 4 first-attempt raw accuracy at observed coverage.

All equivalence rules are committed before submission, including case normalization, unordered-set equivalence, rational normalization, graph-equivalent outputs, and numeric tolerances. Post-reveal rules cannot be introduced merely to change the score.

## First independent suite

The scientific suite contains 12 task families and 600 hidden rows:

- 2 Level 1 families;
- 3 Level 2 families;
- 3 Level 3 families;
- 4 Level 4 families.

Each family contains one opaque task package, a demonstration budget of 3, 5, 10, or 20, exactly 50 hidden rows, at least one adversarial edge case, deterministic row ordering, retained construction evidence, exact targets, and a precommitted scoring specification.

Level 1 may use externally generated familiar primitives. Level 2 uses unfamiliar notation, terminology, schemas, or output forms. Level 3 requires unseen compositions. Level 4 uses genuinely new systems such as an invented board game, custom symbolic language, fictional rules with exceptions and defeaters, or a novel scheduling world.

A family is not Level 4 if materially equivalent generator logic or templates existed in the solver repository or were disclosed to developers before submission.

## Independence attestation

The reveal records evaluator identity or stable pseudonymous key, creation time, source-review status, whether generators derive from repository tests, whether developers saw private material, external-model assistance, hashes of retained generator source and source materials, conflicts of interest, and whether evaluator and auditor are distinct.

For the strongest claim, evaluators must not copy, paraphrase, or parameterize repository test generators.

## Solver restrictions

The scored system is exactly the frozen core or a reproducible build with identical source identity.

Forbidden during a scored attempt:

- source changes after commitment publication;
- manual or task-name routing;
- hidden-target access;
- input-hash answer mappings;
- row-specific exceptions;
- target-informed correction ledgers;
- post-score repairs;
- replacement of the first attempt.

Execution uses pinned dependencies, deterministic seeds, no network access, solver freeze before hidden execution, and exact recording of abstentions and failures.

## Error handling

Any mismatch in suite ID, challenge digest, reveal digest, scoring-policy digest, frozen core, or nonce blocks scoring.

A submission is invalid when task IDs, row counts, ordering, package digests, core identity, or seals differ; when it was created after reveal; or when the first attempt was overwritten.

Evaluator defects require a versioned adjudication record. The original score remains preserved; corrected reports are revisions. Known ambiguity is committed in advance, while unexpected ambiguity is treated as an evaluator defect.

## Evidence package

```text
COMMITMENT.json
PUBLIC_CHALLENGE.json
SUBMISSION.json
PRIVATE_REVEAL.json
SCORE_REPORT.json
INDEPENDENCE_ATTESTATION.json
ENVIRONMENT.json
CORE_IDENTITY.json
AUDIT_MANIFEST.json
SHA256SUMS
attempts/<opaque-task-id>/{SOLVER.json,PREDICTIONS.jsonl,ATTEMPT.json,MANIFEST.json}
```

Every file is covered by a top-level manifest and every task attempt by a nested manifest. The package must reproduce offline without target-generating network calls.

## Architecture

Implement additively under `research/universal_core/blind_eval/`:

```text
contracts.py    protocol dataclasses and validation
commitment.py   nonce and commitment construction
challenge.py    public/private separation
submission.py   frozen-core execution and sealing
reveal.py       reveal and independence verification
scoring.py      deterministic metrics
statistics.py   Wilson intervals and macro aggregation
evidence.py     immutable writes and manifest verification
cli.py          commit, submit, score, and audit commands
```

The package may depend on public Universal Core contracts, canonical serialization, runner, and sealing interfaces. It must not import repository test generators.

## CLI

```bash
python -m universal_core.blind_eval.cli commit --public PUBLIC.json --private REVEAL_DRAFT.json --output COMMITMENT.json
python -m universal_core.blind_eval.cli submit --commitment COMMITMENT.json --challenge PUBLIC.json --core-commit 89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9 --output submission/
python -m universal_core.blind_eval.cli score --commitment COMMITMENT.json --challenge PUBLIC.json --submission submission/SUBMISSION.json --reveal PRIVATE_REVEAL.json --output SCORE_REPORT.json
python -m universal_core.blind_eval.cli audit --evidence blind-eval-evidence.zip
```

The audit command exits nonzero on any digest, schema, ordering, commitment, score, or manifest mismatch.

## Testing and CI

Use TDD and atomic commits.

Unit tests cover canonical serialization, nonce validation, commitment verification, hidden-target rejection, ordering, sealing, reveal verification, equivalence rules, Wilson intervals, immutable writes, and manifests.

Adversarial tests cover changed targets or scoring, nonce mismatch, row reordering, changed predictions, changed core identity, hidden-label injection, family-metadata leakage, task additions or removals, post-reveal exclusions, and first-attempt overwrite.

End-to-end tests perform commit, frozen submission, reveal, score, audit, byte-identical replay, and tamper failure. These fixtures validate the protocol and are not scientific blind results.

CI runs the full Universal Core regression suite, blind-evaluation tests, frozen-core and archive guards, protocol round trip, tamper tests, deterministic replay, prohibited-mechanism scan, SHA-256 manifest generation, and evidence upload.

## Completion criteria

Implementation is complete when all contracts and CLI flows work; commitments prevent target and scoring substitution; the frozen core produces immutable submissions; scoring reproduces offline; Levels 1-4 are mandatory; Level 4 accuracy is prominent; tampering fails deterministically; archive checks pass; and an external evaluator can create a challenge without modifying solver code.

No minimum accuracy is imposed before the first real blind run. The first result must be reported honestly, including low accuracy, abstentions, and unsupported families.

## Immediate boundary

The implementation cycle builds only the protocol, validation, scoring, evidence, CLI, tests, and CI. It does not create the 12-family scientific challenge inside the solver repository. A separate evaluator creates that suite outside this repository after the protocol is verified.
