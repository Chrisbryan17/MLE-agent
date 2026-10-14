# NNN v3: Pilot 002 — First-Attempt Results and Decision

**2026-10-14 Jamaica. Negative against registered +5 pp active-vs-random superiority gate.** The **recorded** 180-case evaluation occurred after source/data/query/prediction commitments. **Protocol caveat identified in the post-score audit:** the frozen unit test also regenerated and scored these identical deterministic seeds in a temporary directory before the recorded first-attempt scoring. We did not inspect those test metrics during development, but this is not a strictly untouched holdout. Treat Pilot 002 as development-repeated synthetic evidence and demand a clean-seed replication. The primary task remains unfinished: NNN has **not** become a frontier-level general reasoning engine.

## Chronology / hard provenance

1. Existing PR #40 verified open, draft and unmerged at `61426a55d096e5e27cc21670e80455aa40482baf`. Frozen V2.1 preserved at `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`. Prior Pilot 001 branch preserved at `cf0b0938e674d8df1cfe8dfea6579e1aaf275ef8`.
2. New branch `research/nnn-v3-generalization-recovery-20261014` created at the Pilot 001 head. Preregistration and frozen implementation committed **before** evaluating the holdout: `b062955b921da7da3ee5e82f7c8ead9ce7bf855e`. Thirteen focused local tests passed.
3. Dataset generation produced **108 visible two-step training tasks** and **180 unseen three-step synthetic compositions** across seeds `9173, 9179, 9187` (60 holdout cases each). Source/public/hidden-oracle and target-label hashes committed at `27331c570d23f61dc3dddfe317b373a0a9dcccbc`, before querying.
4. Query selections for every held-out task committed **before feedback release** at `64f80457bb028bbffa6c7002b18a5b70b76f2a8e`: SHA-256 `c556bd270e74f4b58105605c017a98c047354f7b06f45ac5735fdd9a5207b65a`.
5. Only preselected oracle-query answers were released. All six methods' first test predictions sealed at `dfab9eeb8d1ea30145cc79164602e1f152dbd010`, with SHA-256 `bf343492a873772b2dcfff2a0a7888cc976537892947dff9451082daffbf6715`.
6. **Only then** were held-out test labels opened by the recorded scorer. However, test-stage scoring of the same generated seeds had already occurred without visible metrics. Original `score.json` SHA-256 `7b558d311736479dbaff981cf3432614ea0554187844805efea0bf1bd49d0ced`. Read-only independent `audit.py` recomputed every method total and per-seed effect from the immutable predictions and targets; reproduced public dataset/gold generator; verified feedback matched exactly the sealed query choices.

## Headline: exact test-vector predictions

| System | Correct / 180 | Accuracy | Coverage | Wrong accepted |
|---|---:|---:|---:|---:|
| Active query + full candidate enumeration | **180** | **100.00%** | 100.00% | 0 |
| Full enumeration, no query | 131 | 72.78% | 72.78% | 0 |
| Active query, no learned macro ordering | 129 | 71.67% | 71.67% | 0 |
| Active query + learned macro ordering | 117 | 65.00% | 66.67% | 3 |
| Random query + learned macro ordering | 113 | 62.78% | 63.89% | 2 |
| No query, same limited macro-first search | 94 | 52.22% | 58.89% | 12 |

The **primary** comparison, active vs random with identical 52-candidate and one-query limits, is **+4/180 = +2.22 percentage points**, paired bootstrap 95% **[-0.56 pp, +5.00 pp]**, with McNemar exact p = **0.21875** (discordant cases: active-only 5, random-only 1). **Preregistered superiority gate failed**: gain <5 pp and interval includes zero.

Per-seed comparison: seed 9173 active 38 vs random 36; 9179 active 38 vs random 38; 9187 active 41 vs random 39. All streams were nonnegative, but insufficient evidence of a reproducible meaningful gain.

**Secondary contrasts (exploratory, no multiplicity correction):** active-query macro mode vs no-query macro mode +12.78 pp; relative to active no-macro ordering **-6.67 pp** (macro ranking harmed coverage on this distribution); full enumeration plus active query 100% is an *oracle-feedback plus known-grammar result*, not induction of unexpressible new primitives.

Four additional critical observations:

1. **Learned macros were not an automatically reliable search policy.** Four labeled examples per training task allowed mining 14 recurrent two-step macros, yet prioritizing them under the 52-candidate limit harmed test accuracy compared with simple ordering. Keep this ablation; do not patch macros using opened holdout errors.
2. **One query helps relative to no query, but the fair active-vs-random comparison was inconclusive.** Nontrivial improvement requires information gain under a stronger matched exploration and inference budget, and replication on entirely new task families.
3. **The semantic front end is still unsolved.** `semantics.py` validates already structured facts, provenance, quantifier/negation/time scope, and exposes oracle-vs-predicted scoring. It does not parse unrestricted language, images or authentic source documents. Zero general text-extraction benchmark results exist from this new code.
4. **Holonomy novelty remains unproven.** `transport.py` computes valid modular cycle residuals and robust group-estimation baselines. It has algebraic property tests, not a causally isolated performance advantage over robust group synchronization. Pilot 001's negative result is not reversed by Pilot 002.

## Why the result is NOT frontier/general intelligence

The underlying 5 primitives are predefined; holdout transformations are previously unseen compositions of *known* operators, not previously unexpressible operator families. All inputs are exact length-four symbolic vectors. The evaluation generator is public, and its original unit tests implicitly reexecuted the same deterministic seeds: this invalidates a *strictly untouched* assertion. It remains a reproducible development-controlled diagnostic, not an external blind experiment. The evaluation can be solved completely by known-program enumeration with an additional oracle example. Thus the 100% number makes no claim about generality, real-world knowledge, document semantics, ARC, visual perception, planning, or broad out-of-distribution transfer. Limited search count is **not equal** to matched primitive-step or FLOP cost. The prior/active entropy heuristic and finite macro miner do not match an advanced neural program synthesizer or DreamCoder's wake-sleep learning.

## Decision and stop criterion

**STOP** optimizing on Pilot 002's holdout: it has been opened and is hence development-visible. Preserve all frozen code, predictions, scores and failures. No claim of active-query advantage beyond a narrow inconclusive effect. Do not merge PR #40 and do not add another task-driven ARC primitive.

**Next independent research milestones:**

1. Unseen *primitive-family* induction from a genuinely more expressive metalanguage with strict identifiability conditions, amortized inference baseline, MDL/e-graph abstraction extraction, and multi-seed held-out families (not merely different composition depths).
2. Learned world-to-typed-graph parsing of external document questions with explicit alignment/provenance and graded entity/relation, negation/quantifier and temporal scope metrics; compare to a conventional structured-extraction baseline and report oracle-graph vs predicted-graph downstream delta.
3. Corruption-aware latent group synchronization with robust factor-graph and cycle-edge-message-passing baselines and sufficient-connectivity conditions. Separate algebraic equivalence/nulls from genuinely nontrivial path curvature.
4. Interactive world-model learning, identifiable causal interventions, active queries, planning and calibrated abstention with independently administered holdouts; report actual time, primitive steps, samples and failures.
5. External replication before any generalization or novelty claim; strong baselines including DreamCoder/LAPS and robust group synchronization literature.

*References:* Ellis et al. (2021), DreamCoder, DOI `10.1145/3453483.3454080`; Wong et al. (2021), LAPS, PMLR 139; Lerman & Shi (2022), Robust Group Synchronization via Cycle-Edge Message Passing, *Foundations of Computational Mathematics*, 22:1665–1741.

## Post-score integrity erratum (does not change frozen scores)

A scrutiny pass found that `tests/test_v3.py::test_seal_refuses_overwrites_and_tampering` invoked the same `generate()` fixed seeds and full scoring routine in a temporary directory. Because the tests ran before the recorded first-attempt score, Pilot 002 fails the strict no-prior-label-exposure requirement, **even though we did not read the temporary score or tune from it**. This is material. The code and published Pilot 002 score remain frozen; the repaired evaluation must patch test fixtures to independent development-only seeds and use genuinely fresh held-out seeds on a separately preregistered replication branch. The conclusion here is exploratory, not confirmation.
