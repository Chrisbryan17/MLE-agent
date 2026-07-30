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

## Verification status

Local and hosted test totals, workflow run IDs, job IDs, artifact IDs, artifact digests, and independently verified manifest counts are intentionally absent until exact-head CI succeeds. They will be recorded in one evidence-only commit without changing protocol behavior.

## Known limits

- One opaque task schema per package, matching frozen Universal Core V1.
- Instructions plus 3–20 demonstrations are required.
- External evaluators must retain source and construction evidence.
- The protocol validates integrity and ordering; it does not guarantee benchmark quality.
- No minimum accuracy is imposed on the first real blind evaluation.
