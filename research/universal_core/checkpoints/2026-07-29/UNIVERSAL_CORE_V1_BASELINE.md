# Universal Core V1 Baseline

**Baseline date:** 2026-07-29  
**GitHub verification date:** 2026-07-30  
**Implementation branch:** `universal-core-v1`  
**Design branch:** `universal-core-v1-design`  
**Immutable archive branch:** `archive/universal-bbeh-dual-track-4520-2026-07-28`  
**Immutable archive commit:** `a0c099a41c85f267ca6323235a019b2052107873`

## Claims boundary

This baseline measures a **synthetic private-style holdout** generated inside the development repository. It is useful engineering evidence for unseen rows, randomized task names, varied demonstration budgets, solver freezing, and deterministic replay. It is **not an independent private benchmark**, an external leaderboard result, or proof of universal reasoning.

The archived 4,520-row BBEH system remains separate. Its 4,520/4,520 lane is explicitly public-corpus fit and is never used as Universal Core generalization evidence.

## Implemented contract

Universal Core V1 receives one unknown task schema, natural-language instructions, 3–20 labeled demonstrations, and hidden unlabeled rows. It excludes benchmark names and inert metadata from solver induction, rejects hidden target fields, synthesizes trusted operator or constrained MiniLang programs, verifies candidates, freezes the accepted solver before hidden execution, and seals immutable first-attempt predictions.

## Local baseline evidence

The pre-CI local environment was:

- Python `3.13.5`;
- pytest `9.0.2`;
- Z3 unavailable locally, with the deterministic finite-domain fallback exercised instead;
- **84 tests passing** after the Task 15 CI-contract tests were added;
- sealed sample attempts byte-identical across independent replay;
- zero modified or deleted archived files in the implementation workspace;
- fixed release report digest `fafbbd0ff75cdf3fb2759e5c518da8f66ff1dc97abe7ac42a3d64178fcd572db`.

The fixed release harness evaluates:

- **1,000 exact hidden rows** across affine arithmetic, record sorting, filter/count, graph reachability, and finite ordering;
- **300 lightweight-semantic hidden rows** across explicit keyword-relation classification;
- demonstration budgets of 3, 5, 10, and 20 for exact families, and 3, 5, and 20 for the semantic family;
- randomized task names, demonstration reordering, unseen input hashes, and prohibited-route scans.

| Lane | Correct | Attempted | Rows | Accuracy | Coverage |
|---|---:|---:|---:|---:|---:|
| Exact generated holdout | 1,000 | 1,000 | 1,000 | 100% | 100% |
| Lightweight-semantic generated holdout | 300 | 300 | 300 | 100% | 100% |
| Combined | 1,300 | 1,300 | 1,300 | 100% | 100% |

These scores are internal generated-holdout evidence under the claims boundary above.

The release gates were fixed before GitHub-hosted execution:

| Gate | Threshold | Verified result |
|---|---:|---:|
| Exact generated-hidden accuracy | at least 95% | 100% |
| Lightweight-semantic generated-hidden accuracy | at least 80% | 100% |
| Overall coverage | at least 90% | 100% |
| Deterministic replay | 100% | 100% |
| Task-name and metadata invariance | 100% | 100% |
| Security-policy violations | 0 | 0 |
| Archive-regression failures | 0 | 0 |

## GitHub-hosted verification

The final-head GitHub-hosted reproduction ran against implementation head `d3fbca8671551748510dd52cd947386495632f49`.

- Workflow: `Universal Core V1`
- GitHub Actions run: `30518496930`
- Job: `verify` (`90793532663`)
- Runtime: CPython `3.12.13`
- pytest: `9.0.2`
- Z3: `4.15.3`
- Tests: **84 passed**, 0 failed, 0 skipped, 0 errors
- Exact generated holdout: **1,000/1,000**
- Lightweight-semantic generated holdout: **300/300**
- Combined generated holdout: **1,300/1,300**, 100% coverage
- Release report digest: `fafbbd0ff75cdf3fb2759e5c518da8f66ff1dc97abe7ac42a3d64178fcd572db`
- Artifact: `universal-core-v1-evidence` (`8749812327`)
- Artifact size: `92,559` bytes
- Artifact digest: `sha256:6b9a3944389e2fb53b869ca86ad14f76414e6c8b90eed6a2e1763b625389c2b4`
- Archive verification: exact branch and commit match; zero deleted protected paths
- Prohibited-mechanism scan: zero findings
- Sealed sample replay: byte-identical

Independent artifact verification reproduced the ZIP digest, matched all **83** top-level SHA-256 manifest entries, matched all **25** nested sealed-attempt manifests, and found zero digest mismatches. Both independently reproduced sample attempts had the same solver digest `933ddd418151790123477a6a6de4d3c90d4da996da3d853147679ef8fc74e668` and prediction digest `5d236ed04e603f77e33fd8c0cfe8a190a8bf3d1b74788c37b13b8390d44ae597`.

## Known V1 limits

- One unknown task schema per batch.
- Instructions plus demonstrations are required; instruction-only induction is future work.
- Semantic coverage is intentionally limited to lightweight, context-contained classification.
- The constrained MiniLang fallback is deliberately smaller than Python.
- The built-in proposal backend is deterministic and heuristic; external learned proposal backends require separately frozen prompts and provenance.
- Independently held task families remain the decisive next scientific test.
