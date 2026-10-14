# Pilot 001: First Sealed Controlled Experiment and Decision Memo

**Date:** 2026-10-14 (Jamaica). **Outcome: negative for holonomy-specific superiority in the tested setting.** The frozen Universal Core and ARC V2.2 implementation were not edited or run on ARC test labels. This is a new, separate synthetic transport pilot, not a benchmark score for existing NNN.

## Provenance and sealed chronology

1. Audited repo head and original draft PR #40: `61426a55d096e5e27cc21670e80455aa40482baf`; frozen V2.1: `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`. Verified PR #40, #39, #38 and #37 remain open draft; original successful 2026-08-15 run `31913042297`, artifact `9254269593` available with digest `sha256:059e2458595c5153f37684f7e73b027c38a4fe7c8a8c58b0eee371782ca9eb8f`.
2. Created new branch `research/holonomy-causal-ood-pilot-20261014` directly from that head. Exact implementation, tests and preregistration committed prior to evaluation. Git blobs matched local `git hash-object` results.
3. `prepare` generated 420 train/development and 300 structurally withheld cases across three seed streams. The immutable public-data hash and held-out gold-label commitment were committed to the new research branch at `413c6a376c59315f3cb5379d6f3ebb2ac37bd4dc` **before inference**. They are:
   - Code SHA-256: `66e80d5ae7fb44451133bea6e2fe80429ad85f302eb5a7271a519c981892c925`.
   - Public data SHA-256: `8f5f49ab064457a3631986507510f9a5630325ec68b74d943e7dc67ae7a5b936`.
   - Sealed gold-label SHA-256: `d99a4924cb53de8133951735e564975bc237c4b022f723d5fa57922d778dd808`.
4. Prediction stage read public inputs and train labels only, never held-out labels; saved all 300 first-attempt predictions at SHA-256 `36767747b5d628b876cafe928232d62f436f827facdda616c8377570052c1e60`. This digest was publicly committed at `f8a488ecb44e78fdbc5fe0aef1761d3b3a8762a2` **before scoring**.
5. Scored once, with first-attempt score SHA-256 `8029e66365632330593c1b9cad5cfac9ef6bebb6f6323b1c0888844501bce649`. Post-score read-only integrity audit independently recomputed totals, split length constraints and prediction equality. An original per-seed metric bug was identified and is corrected below **without altering the original frozen scorer, score file or prediction file**.

## Results: 300 held-out long-composition cases

| Method | Correct | Accepted | Wrong accepted | Raw accuracy | 95% Wilson accuracy | Coverage | Attempted accuracy |
|---|---:|---:|---:|---:|---|---:|---:|
| Graph search, shortest path | 225 | 300 | 75 | **75.00%** | [69.80%, 79.56%] | 100.00% | 75.00% |
| Learned affine-program ranker | 216 | 285 | 69 | 72.00% | [66.67%, 76.78%] | 95.00% | 75.79% |
| Holonomy identity-loop consistency | 203 | 244 | 41 | 67.67% | [62.18%, 72.71%] | 81.33% | 83.20% |
| Matched finite affine DSL enumerator | 203 | 244 | 41 | 67.67% | [62.18%, 72.71%] | 81.33% | 83.20% |
| Noisy transport ablation | 168 | 220 | 52 | 56.00% | [50.34%, 61.51%] | 73.33% | 76.36% |
| No-composition ablation | 0 | 0 | 0 | 0.00% | [0%, 1.26%] | 0.00% | undefined |

All methods other than noise-injected and composition-removed ablations achieved 150/150 correct in the zero-noise regime. With 15% corrupted observed edges (150 cases), holonomy and DSL reached 53/150 (35.33% raw), shortest-path graph search 75/150 (50%), and learned ranker 66/150 (44%). This noisy regime is where most differences occur. Individual path votes share edges and are correlated, so maximizing agreement can amplify a corrupted common edge rather than denoise it.

**Paired holonomy vs graph search**: holonomy-only correct 5 cases, graph-only correct 27 cases; exact two-sided McNemar p = 0.000113; raw difference **-7.33 percentage points**, paired bootstrap 95% interval **[-11.00, -3.67] percentage points** (nominal; best-baseline selection not multiplicity-adjusted). Holonomy vs DSL: **every one of the 300 predictions was identical**, confirmed separately by a read-only audit. This is algebraically expected because for exact invertible maps a closed comparison loop is equivalent to equality of the two composed path maps.

## Corrected per-stream effect (post-score reporting erratum)

The preregistered scorer incorrectly used a `startswith()` prefix containing the entire initial case ID, selecting only one case from each stream for `per_seed_effects`. The original `score.json` has `[0,0,0]`, **which must not be used**. A separate read-only `audit.py` reports:

| Seed | Cases | Holonomy correct | Graph correct | Holonomy − graph |
|---|---:|---:|---:|---:|
| 8101 | 100 | 65 | 75 | **-10.00 pp** |
| 8102 | 100 | 73 | 79 | **-6.00 pp** |
| 8103 | 100 | 65 | 71 | **-6.00 pp** |

The audit verifies that all 300 query shortest-path distances are 4, 5 or 6 while development queries are at most 2; held-out IDs are unique; label and prediction digests match the sealed commitments; and the aggregate reported method scores agree with recomputation. The preregistered superiority gate fails whether using original or corrected per-seed effects.

## Search cost, calibration and limitations

The original score records median per-query latency (machine-specific wall-clock) and mean scored operations. Graph search: **17,221 ns** / **4.20 operations**; holonomy: **26,965 ns** / **8.28**; DSL: **21,637 ns** / **16.56**; learned ranker: **23,690 ns** / **8.28**. The operations have different semantics by method, so they are **not** a universal hardware-normalized compute budget. Every method had the same 32-path/7-hop search cap and input graph. Brier and risk-at-coverage arrays are preserved unrounded or with specified rounding in `score.json`; confidence fractions are proxies, not calibrated probabilities. The output JSON contains timing fields, so its SHA-256 is an immutable **first-attempt artifact digest**, not an expected byte-identical digest on other machines.

The 300 held-out cases are synthetically generated under the same known affine grammar; graph topologies and composition lengths differ, but transformation *operator families do not*. The learned synthesizer is a modest supervised three-feature program ranker, not a comparable large generative foundation model. Exact oracle typed-graph inputs bypass language, extraction and provenance. The pilot is **not the native V2.1/V2.2 engine**, has no independently administered hidden dataset, cannot certify universal reasoning, and cannot establish novelty relative to the literature. The narrow null does **not** disprove all possible uses of holonomy.

## Decision and next experiment

**Decision:** The pre-registered +5 pp superiority threshold versus the strongest simpler method fails. Here the holonomy scorer is mathematically redundant with path-vote/DSL consistency and loses raw accuracy to shortest-path search under shared-edge corruption. Retire the claim that loop-closure scoring alone is a unique generalization advance **for exact affine graph transports**. Preserve the broader theory as an open hypothesis, not a measured success.

**Next priority:** Causally test a genuinely non-redundant holonomy mechanism, e.g. recovery of latent transformations from *partial*, noisy observations where algebraic cycle constraints provide independent information unavailable to flat path voting. Freeze a matched graph-estimation optimizer, DSL solver and learned baseline before testing separately generated unseen operator and composition families. In parallel, start an entirely separate **world-to-typed-graph semantic induction** benchmark on genuine external documents, with provenance and scope accuracy and oracle-vs-inferred downstream deltas. No new ARC-specific primitive patches. Keep PR #40 draft and do not merge existing work.
