# Blind Evaluation Protocol V1 Checkpoint

**Protocol:** `universal-core-blind-eval-v1`  
**Frozen core:** `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`  
**Preserved archive:** `archive/universal-bbeh-dual-track-4520-2026-07-28` at `a0c099a41c85f267ca6323235a019b2052107873`

## Scope

This checkpoint covers the cryptographic commit-predict-reveal protocol, public/private separation, immutable frozen-core submission, reveal verification, deterministic equivalence rules, Level 1–4 scoring, evidence manifests, offline audit, CLI, adversarial tests, and GitHub-hosted reproduction.

The repository fixture is **protocol mechanics** evidence only. It is **not an independent blind benchmark**, and this checkpoint contains **no scientific accuracy result**. The real 12-family, 600-row suite must be created outside the solver repository after the protocol is frozen.

## Claims boundary

A successful protocol run can establish that an evaluator committed to challenge, targets, scoring rules, nonce, and provenance before submission; the frozen core produced an immutable first attempt before reveal; and an auditor reproduced the score from sealed artifacts. It cannot establish unrestricted universal reasoning without an independently created challenge.

## Implemented contracts

- `ChallengeCommitment`
- `PublicChallengeSuite`
- `SubmissionEnvelope`
- `PrivateReveal`
- `ScoringPolicy`
- `IndependenceAttestation`
- `SCORE_REPORT.json`
- recursive evidence manifests and deterministic ZIP

## External evaluator procedure

1. Create task families, hidden targets, scoring rules, provenance, and nonce outside this repository.
2. Publish `COMMITMENT.json` and the public challenge digest before providing the public challenge.
3. Receive and externally timestamp the sealed `SUBMISSION.json` digest.
4. Reveal the committed private package only after submission sealing.
5. Run deterministic scoring and independent offline audit.
6. Report Levels 1–4 separately, with Level 4 first-attempt raw accuracy at observed coverage as the headline metric.

## GitHub-hosted protocol verification

The behaviorally complete protocol head was `fa3beeaa4eecd9a1d90089a29055f92b133e6753`.

- Blind-evaluation workflow run: `30543220433`
- Blind-evaluation job: `90872773776`
- Frozen Universal Core regression workflow run: `30543220430`
- Frozen Universal Core regression job: `90872773822`
- Frozen-core tests: **84 passed**, 0 failed, 0 errors, 0 skipped
- Blind-protocol tests: **41 passed**, 0 failed, 0 errors, 0 skipped
- Combined test total: **125 passed**
- Archive identity and protected-path verification: passed
- Frozen top-level Universal Core production-byte verification: passed
- Prohibited-mechanism scan: zero findings
- Tamper-matrix tests: **3 passed**
- Protocol fixture replays: byte-identical

Hosted artifact:

- Name: `universal-core-blind-eval-v1-evidence`
- Artifact ID: `8759571928`
- Size: `66,272` bytes
- Artifact digest: `sha256:70a4bde52f06aad4b1c5edf718edfd5b4e85630fbbefc0c00ce4349d2eb8e0b4`
- Deterministic nested evidence ZIP digest: `sha256:9b9c8c8b54b168a4fc06eef2d2214a6438601122d5859ac875ce1befb20e4ed1`

Independent artifact verification found:

- **60/60** top-level `SHA256SUMS` entries matched;
- two byte-identical protocol replays;
- **13/13** nested checksum entries matched in each replay;
- **12/12** nested audit-manifest entries matched in each replay;
- one sealed attempt manifest per replay with zero mismatches;
- commitment, public-challenge binding, private-reveal, submission, score-report, prediction, and solver-freeze digests all matched;
- zero unsafe ZIP paths.

The mechanics fixture contained one Level 1 affine task with three hidden rows, all scored correctly. Levels 2–4 contained zero rows. That fixture score validates plumbing only and must never be represented as blind generalization performance.

The evidence-only checkpoint commit that contains this section is revalidated by the same complete workflows. Because a commit cannot contain the future run and artifact identifiers generated after that commit exists, the draft PR metadata records the exact final documentation-head run and artifact without another source commit.

## Known limits

- One opaque task schema per package, matching frozen Universal Core V1.
- Instructions plus 3–20 demonstrations are required.
- External evaluators must retain source and construction evidence.
- The protocol validates integrity and ordering; it does not guarantee benchmark quality.
- No minimum accuracy is imposed on the first real blind evaluation.
