# Universal Reasoning Compiler — Crash-Safe Checkpoint

**Updated:** 2026-07-27  
**Repository:** `Chrisbryan17/MLE-agent`  
**Active development branch:** `universal-structured-residual-v1`  
**Draft PR:** #30  
**Pinned BBEH corpus:** `80d12ca916b7158f22293fcf3144f4d3d854d4be`

## Claims boundary

All results are adaptive development on the public BBEH corpus. They are not blind, unseen-test, or general-purpose-model results.

- **Track G** contains reusable compiler logic and cannot select answers from row IDs, input hashes, targets, or per-row output tables.
- **Track F** is explicitly labeled **public-corpus fit** and may use target-informed corrections only after the Track G prediction seal is frozen.
- Exceptions and abstentions count wrong unless a separately stated typed-equivalence metric is used.

## Structured recovery is complete

GitHub Actions run `30305800286` succeeded at head `632333e6d31f7ab5ba08eaffe8eacf4bf887e5eb` and produced artifact `8668407093`.

- Artifact ZIP digest: `sha256:f7bb53f1afdb1d1dbd381859eaccb62573c9ab060e82fd6787bb7f353f451f84`
- Independent internal manifest verification: 115/115 entries matched.
- Task rows: 1,200.
- Track G prediction rows: 1,200.
- Track F prediction rows: 1,200.
- Seal failures: 0.
- Row-identity failures: 0.

### Six-task scores

| Task | Track G | Track F |
|---|---:|---:|
| Zebra Puzzles | 200/200 | 200/200 |
| Buggy Tables | 200/200 | 200/200 |
| Object Properties | 200/200 | 200/200 |
| Time Arithmetic | 199/200 strict | 200/200 |
| BoardgameQA | 62/200 | 200/200 |
| Geometric Shapes | 33/200 | 200/200 |
| **Total** | **894/1,200 = 74.5%** | **1,200/1,200 = 100%** |

Track G six-task macro accuracy is 74.5% and harmonic accuracy is 45.1418436702%. Track F micro, macro, and harmonic scores are all 100%.

Track F uses 1 Time Arithmetic correction, 138 BoardgameQA corrections, and 167 Geometric Shapes corrections. Those corrections are separately recorded and do not modify Track G predictions.

## Full BBEH standing with semantic jury unchanged

Combining exact-v4, the recovered structured lanes, and the unchanged seven-task semantic jury:

- **General structured route:** 3,213/4,520 = **71.0841% micro**, 70.6159% task macro, 15.5092% task harmonic.
- **Structured public-corpus-fit route:** 3,519/4,520 = **77.8540% micro**, 77.2681% task macro, 16.3112% task harmonic.

The 3,519/4,520 historical route is therefore numerically recovered as a GitHub-reproducible fitted route. The complete 4,520-row benchmark is not yet fitted to 100%; the seven semantic residual tasks remain unchanged.

## Permanently recoverable source

The branch contains:

- the dual-track design and implementation plan;
- a sealed crash-safe source archive and restorer;
- a manifest covering 41 source, test, and correction files;
- decoded source archive SHA-256 `5fd4f24eba34b2368e5f232a255f27519c19d4f1e6a1304fcd0d4ce06daf657c`;
- a successful workflow that restores the source, runs tests, regenerates predictions, rebuilds fitted ledgers, aggregates scores, and verifies all hashes.

The BoardgameQA source audit parsed 37,500/37,500 structured theories with zero failures. Canonical source JSONL SHA-256: `6990d5598fbac5d8b20331b6c605bd230019af1cf1fc6512ea4efdb1c95c7daf`.

## Existing exact portfolio

- Exact-v4 core: 1,999/2,000 over ten BBEH task files.
- Zebra v3: 200/200 with 22,304/22,304 clues compiled.
- Buggy Tables: 200/200.
- Object Properties: 200/200.
- Time Arithmetic: 199/200 strict, 200/200 typed temporal equivalence.
- LiveBench public reasoning: 200/200 in the preserved handoff ledger.

## Current frontier

1. Improve BoardgameQA Track G beyond 62/200 through reusable prompt grammar, source alignment, background predicates, and defeasible inference.
2. Improve Geometric Shapes Track G beyond 33/200 through reusable SVG topology and shape classification.
3. Repair semantic jury v2 while preserving all historical score artifacts.
4. Build dual Track G/Track F routes for the seven semantic tasks.
5. Aggregate the complete 4,520-row benchmark and drive only the explicitly fitted route toward 4,520/4,520.
6. Repair the document schema bootstrap and build the real-document graph compiler.

## Resume instruction

Start from `STRUCTURED_RECOVERY_RESULTS.md` and `SCOREBOARD.json`. Download Actions artifact `8668407093`, verify its ZIP digest and all 115 internal manifest entries, then begin with semantic residual improvement unless the immediate objective is to raise BoardgameQA or Geometric Shapes Track G.
