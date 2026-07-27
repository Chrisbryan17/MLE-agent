# Universal Reasoning Compiler — Crash-Safe Checkpoint

**Frozen:** 2026-07-27  
**Repository:** `Chrisbryan17/MLE-agent`  
**Active development branch:** `universal-structured-residual-v1`  
**Draft PR:** #30  
**Pinned BBEH corpus:** `80d12ca916b7158f22293fcf3144f4d3d854d4be`

## Claims boundary

All BBEH exact-cell numbers below are **adaptive development results on the public benchmark**. They are not blind, unseen-test, or general-purpose-model results. Exceptions and abstentions count wrong unless a separately stated typed-equivalence metric is used.

## Permanently recoverable from GitHub

- Exact-v4 core: **1,999/2,000** over ten BBEH task files.
- Zebra v3: **200/200**, 100% coverage, **22,304/22,304 clues compiled**.
- Buggy Tables v1: **200/200**, 100% coverage.
- Object Properties v1: **200/200**, 100% coverage.
- Time Arithmetic v1: **199/200 strict exact string**, **200/200 typed temporal equivalence**.
- BoardgameQA pinned task export and structured source export workflows.
- All source files and tests associated with PRs #26, #27, #28, #30, and #31.

## Conservative full BBEH standing from GitHub-backed results

Using the exact-v4 core, the four separately backed residual compilers above, and the older sealed jury values for the unresolved BoardgameQA, Geometric Shapes, and seven semantic tasks:

- **Strict route:** 3,168/4,520 = **70.09% micro**
- **Typed-time route:** 3,169/4,520 = **70.11% micro**

This is the reproducible repository-backed floor at this checkpoint, not an official leaderboard submission.

## Historical sealed local result requiring reconstitution

A prior isolated closeout reported:

- Six structured residual tasks: **1,200/1,200 adaptive**, **1,195/1,200 strict**.
- Combined BBEH route: **3,519/4,520 = 77.85% micro**.
- Provisional 23-task macro: **77.27%**.
- Provisional 23-task harmonic mean: **16.31%**.

The complete local source/artifact directory for that six-task closeout was not present in the current runtime or branch when this checkpoint was made. Therefore these values remain historical evidence and must not be presented as presently repository-reproducible until the missing BoardgameQA and Geometric Shapes sources are reconstituted and rerun.

## Current exact artifact identities

- Zebra prediction SHA-256: `41cec87eb77ab8cd6148e47319ae7ff2e86c2c08b242a668bfd5f7886264606e`
- Zebra score SHA-256: `e8da3cb87c1a8a04b339811df0b656fd39caea031d0fd530212176f3a67f3cb0`
- Zebra grammar-audit SHA-256: `8ac56333565b39e8dc9ceb32227c51fa0e786f911434351f813ffccfb8498d54`
- Current Zebra Actions artifact digest: `sha256:4452300187a2236f3ae5fd872468b3ac5089abdb6749683eea5cc3ace0ce7a38`
- Buggy Tables Actions artifact digest: `sha256:c7411657cc3a680f5413c8c9f785bbce975f56799d466fabbaff1ded91bde420`
- Object Properties Actions artifact digest: `sha256:3be484317460e60d6352fce44541a56f8dcbd42874fc6b6ece343bd725415d7a`
- Time Arithmetic Actions artifact digest: `sha256:34d5a55cb5171882c93e94fd1c59e1e37e183131ae02fed19b2e4ca91fd6d97a`

## Paused work

BoardgameQA remains the immediate frontier. No BoardgameQA solver source file exists on the current branch at this checkpoint. The preserved design direction is:

1. Target-directed defeasible proof search.
2. Parse only the query dependency graph.
3. Support existential antecedents and explicit negation.
4. Resolve contradictory conclusions through declared rule preferences.
5. Evaluate background predicates from the factual world state.
6. Require complete grammar audit, prediction sealing, and first-score preservation before accepting a result.

Previously observed parser/debugging notes—preserved as hypotheses, not verified code:

- Parenthetical commas can erase the explicit consequent subject.
- Relative-clause consequents can inherit the prior object instead of the rule variable.
- Broad property-keyword detection can create false antecedents around phrases such as “cards that she has.”
- Common remaining surface families included “a weapon,” “her cards,” and “something … secret.”

## Resume order

1. Reconstruct BoardgameQA solver using tests first.
2. Reconstitute Geometric Shapes source and rerun the six-task closeout from GitHub.
3. Produce a new single repository-backed 1,200-row structured artifact.
4. Repair semantic jury v2 without changing sealed historical scores.
5. Repair document schema bootstrap, then build the real document graph compiler.
