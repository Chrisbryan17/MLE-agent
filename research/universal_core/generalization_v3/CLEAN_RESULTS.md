# NNN v3 Pilot 003: Clean-seed replication, first-attempt results

**Date:** 2026-10-14 Jamaica. **Outcome: preregistered +5 pp active-vs-random gate failed.** The replication repairs Pilot 002's inadvertent unit-test seed exposure. This remains an *internal, synthetic, known-grammar composition holdout*, not an externally administered or real-world generalization benchmark.

## Provenance and chronological protections

- Parent Pilot 002 and its erratum preserved at `110d21462f23976ede5abaddfc0d5e734e270705` (and its original Pilot 002 code at `b062955b921da7da3ee5e82f7c8ead9ce7bf855e`).
- Frozen clean implementation and preregistration committed at `85bded8f6d9fe358775917de84cb804d2a30c96d`, before evaluation generation or held-out scoring. Identical inference/search/active-query algorithms and budget to Pilot 002; only protocol label, official seed tuple and disjoint test-seed patch differ.
- Official seeds **10103, 10111, 10141**; unit tests patch official generator to **3331, 3337, 3343** before generating or scoring, so all 13 tests passed without opening evaluation labels. Holdout count 180, 60 per seed, 108 training tasks total.
- GitHub data/label/oracle commitments `a703011ec98fde2aa4784471b30119b46306652d` (label SHA-256 `338b0c1696dfb84937a501c96fbafd0cf879a0821c93dc1617962eb28da819f6`). Query proposal digest `0613c1512db32df460e68832bb6c72cf870625f0b827179163f64a2f434addaf`, committed at `d0871b7ac54cd8ad3858366d1dde9a593dfb036f` **before feedback**.
- The first 180 predictions were sealed at `1383889d20bf0ad95c5b9136f0eb3c23ba499492`, SHA-256 `f6cd4d5006e86cf84c4a3e31c0ca6aa3d588d55a28febc9c6160a9fab5ba55cb`, **before opening test labels**.
- First scored report SHA-256 `59e2c8ed343b79f5e14a6c9c5ffe052bd0d0914c718130339460d81fcdde40be`. Separate read-only `audit.py` verified hash commitments, deterministic re-generation, exact matching of query feedback, method correctness totals and per-seed accounting. All 13 tests also pass on GitHub Actions under Python 3.12 (run `38526006740`).

## Results on 180 unseen compositions, known five-operator grammar

| Method | Correct | Raw accuracy | Coverage | Wrong accepted |
|---|---:|---:|---:|---:|
| Full enumeration + active query | 180/180 | **100.00%** | 100.00% | 0 |
| Active query + macros, limited budget | 125/180 | **69.44%** | 70.56% | 2 |
| Active query without macros, limited budget | 126/180 | 70.00% | 72.22% | 4 |
| Random query + macros, limited budget | 119/180 | 66.11% | 68.33% | 4 |
| Full enumeration, no query | 112/180 | 62.22% | 64.44% | 4 |
| Limited search, no query | 90/180 | 50.00% | 58.89% | 16 |

**Primary comparison** (same observations, candidate ordering and one-query budget): active vs random **+6/180 = +3.33 percentage points**; paired bootstrap 95% interval **[+1.11, +6.11] pp**, exact two-sided McNemar p = **0.03125** (6 active-only correct vs 0 random-only correct). The **precommitted +5 pp threshold fails** despite the nominal interval being positive. Three seed effects: 10103 **47 vs 42**, 10111 **38 vs 38**, 10141 **40 vs 39**. This is not an across-families independent scientific claim, and the unadjusted p-value should not be treated as discovery confirmation.

**Independent replication pattern:** Pilot 002 active gain +2.22 pp; clean Pilot 003 gain +3.33 pp. Both fail the +5 pp criterion. The macro-ordering ablation for Pilot 003 is active 125 vs no-macro 126, **-0.56 pp**, consistent with the absence of demonstrated macro benefit in Pilot 002 (which showed -6.67 pp). Do not post-hoc optimize those failures using either holdout.

**Secondary exploratory effects:** active +19.44 pp versus limited no-query search, but this adds an extra oracle observation. Full enumeration + one active oracle query attains 100%, a ceiling result for *already-expressible* compositions, not operator invention.

## Unsolved capability gaps / scientific decision

1. **Operator invention**: not solved. Only new sequences from five supplied operators; the system cannot synthesize an operator outside that finite grammar. Learned macros are repeated strings of known primitives, not a universal abstraction discovery algorithm.
2. **Semantic front end**: not solved. The current module validates typed, provenance-linked fact objects but does not interpret real language, documents or multimodal observations.
3. **Holonomy**: Pilot 001 showed no unique advantage in affine path voting. Modular cycle tests are implemented, but no new statistically supported result against robust global synchronization / cycle message passing exists.
4. **Open-world causal planning**: not implemented. There is no full causal world model, active physical intervention simulation or general hierarchical planning.
5. **Statistical evidence**: these are synthetic internally controlled benchmarks with no independently administered holdout, training-data audit of foundation models or cross-domain replication. Search budget is matched by candidate count, not hardware FLOPs/primitive operations.

**Decision:** preserve the corrected evaluation infrastructure; stop treating the finite DSL's 100% as evidence of general reasoning. Next independently preregistered scientific milestone is new primitive-family induction with a more expressive typed DSL or lambda calculus and a genuine learned semantic front end evaluated on external document problems. Maintain honest null reporting and preserve draft PR #40 and frozen V2.1 unchanged.
