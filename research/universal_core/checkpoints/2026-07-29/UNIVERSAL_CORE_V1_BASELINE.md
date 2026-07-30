# Universal Core V1 Baseline

**Baseline date:** 2026-07-29  
**Implementation branch:** `universal-core-v1`  
**Design branch:** `universal-core-v1-design`  
**Implementation parent through Task 14:** `c34591a4cfbc69d84590f64c813dbc911385a703`  
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


The local fixed release harness produced:

| Lane | Correct | Attempted | Rows | Accuracy | Coverage |
|---|---:|---:|---:|---:|---:|
| Exact generated holdout | 1,000 | 1,000 | 1,000 | 100% | 100% |
| Lightweight-semantic generated holdout | 300 | 300 | 300 | 100% | 100% |
| Combined | 1,300 | 1,300 | 1,300 | 100% | 100% |

These scores are internal generated-holdout evidence under the claims boundary above.

The release gates are fixed before GitHub-hosted execution:

| Gate | Threshold |
|---|---:|
| Exact generated-hidden accuracy | at least 95% |
| Lightweight-semantic generated-hidden accuracy | at least 80% |
| Overall coverage | at least 90% |
| Deterministic replay | 100% |
| Task-name and metadata invariance | 100% |
| Security-policy violations | 0 |
| Archive-regression failures | 0 |

## GitHub-hosted evidence protocol

The workflow `.github/workflows/universal-core-v1.yml` must succeed on Python 3.12 with pytest 9.0.2 and z3-solver 4.15.3.0. It fetches the immutable archive reference, verifies the exact archive commit and non-deletion policy, runs the complete test suite, generates the 1,300-row release report, reproduces a sealed sample twice, scans for prohibited mechanisms, builds a SHA-256 evidence manifest, and uploads `universal-core-v1-evidence`.

At this document's initial commit, no successful GitHub Actions run or artifact existed yet. The draft PR must remain draft until a follow-up evidence-only commit records the actual workflow run ID, artifact ID, artifact digest, final test count, release-gate scores, and independent artifact verification.

## Known V1 limits

- One unknown task schema per batch.
- Instructions plus demonstrations are required; instruction-only induction is future work.
- Semantic coverage is intentionally limited to lightweight, context-contained classification.
- The constrained MiniLang fallback is deliberately smaller than Python.
- The built-in proposal backend is deterministic and heuristic; external learned proposal backends require separately frozen prompts and provenance.
- Independently held task families remain the decisive next scientific test.
