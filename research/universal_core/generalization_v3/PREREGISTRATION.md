# NNN v3 Recovery: Active Compositional Program Induction Pilot 002

**Protocol frozen:** 2026-10-14, prior to held-out prediction or scoring. **Parent:** `research/holonomy-causal-ood-pilot-20261014` at `cf0b0938e674d8df1cfe8dfea6579e1aaf275ef8`. **New branch:** `research/nnn-v3-generalization-recovery-20261014`.

## What this tests and what it does not

**Claim tested:** On entirely new three-step compositions of a known finite operator vocabulary, does budget-limited inference plus active information-gain queries outperform matched random-query induction? This is a narrow, falsifiable version of the missing information-acquisition and compositional-induction capabilities.

**Null:** active querying confers no reproducible positive raw test accuracy over a random query with the same input pool, program budget and one-query allowance. **Not tested:** invention of previously unexpressible primitive operations; visual or unrestricted language understanding; genuine real-world transfer; superiority to DreamCoder or contemporary frontier models; novelty of Bayesian experimental design or group synchronization.

## Methods and preregistered data

Finite program interpreter over length-4 vectors on Z/7Z. Five primitive operations (`roll`, `reverse`, `inc_first`, `inc_last`, `swap_mid`), composed in sequence. Three seeds: 9173/9179/9187. For each stream: 36 two-operation *training* tasks with four labeled demonstrations; 60 *holdout* tasks from three-operation functions whose diagnostic signatures do not match any <=2-operation training function, with only one demonstration. Holdout tasks receive a test input and 12 unlabeled candidate queries. Total: 108 training tasks and 180 held-out test tasks. The generator is synthetic and public. No ARC or external labels are used.

**Canonical-equivalence control:** programs are deduplicated by eight predetermined input probes. Holdout signatures absent from <=2-operation program signatures. This is only a *probe-based approximation* of semantic equivalence and may miss collisions outside those probes; no claim that all 180 test tasks are different program families.

**No hidden-primitive exposure:** holdout compositions can be expressed with the fixed known operator vocabulary; this is a composition holdout, *not* a held-out primitive-family experiment. Full enumeration to depth three is provided as a high-budget comparator. There is no access to a latent language model or external training corpus.

## Compared conditions

- `no_query`: inference from one demonstration, 52 candidate-program evaluations with training-derived macro-first ordering.
- `random_query`: the same 52-program ordering plus one query chosen by deterministic hash of the public task ID.
- `active_query`: the same 52-program ordering plus one query chosen by maximum predictive outcome entropy among hypotheses fitting the demonstration.
- `active_no_macros`: active query, no library prioritization, same 52-program budget.
- `full_no_query`: no query, exhaustive deduplicated depth-three grammar, a costly upper-bound comparator.
- `active_full`: one active query with exhaustive deduplicated depth-three grammar (the strongest feasible baseline in this pilot).

**Budget caveat:** The 52 cap matches candidate count, not operation or wall-clock time; macro-first ordering has preprocessing cost, and active selection has additional query-evaluation overhead. It is not a compute-matched frontier comparison. All query-using methods receive exactly one oracle answer, drawn from the identical public 12-input query pool.

## Sealing and evaluation

1. Commit this preregistration and implementation to the new branch before preparing/inspecting scores.
2. `prepare`: create `public.json`, `sealed_test_labels.json` and `sealed_query_oracle.json`; commit `commitments.json` recording file and source SHA-256 digests before first queries.
3. `queries`: generate `queries.json` from public inputs only. Commit query digest before permitting any query answers to be returned.
4. `feedback`: using a verified committed query digest, release **only** the selected oracle query answers (never test labels).
5. `predict`: use public observations, selected queries, and answers; seal `predictions.json` digest in GitHub **before** `score`.
6. `score`: verify committed prediction digest, open `sealed_test_labels.json` once, produce report and preserve it unchanged. No tuning on this holdout after reveal. Do not rename it blind externally administered scoring; this is a deterministic synthetic within-project holdout.

**Primary metric:** raw exact prediction accuracy over all 180 cases; abstentions count incorrect. Also report coverage, wrong accepted, selective accuracy, Wilson 95% accuracy intervals, per-seed accuracy, Brier proxy and paired effects. Compare active vs random query with 3,000 paired bootstrap draws (seed `20261014`) and exact discordance-based McNemar p-value. Calibration is a *proxy* from discrete candidate-support fractions, not validated probability calibration.

**Primary gate (must meet all):** active minus random >= +5 absolute percentage points; paired-bootstrap lower 95% endpoint >0; and active >= random in all three seed streams. Failure triggers an explicit negative/inconclusive result; no post-hoc adjustment using the same holdout. Secondary comparisons with no-query, no-macro and full enumeration are exploratory and must be reported regardless of whether favorable.

## Additional modules / stop conditions

`semantics.py` implements only structured typed evidence validation, explicit scope, temporal bounds, provenance, extraction exact-match and a tiny existential evidence lookup. This **does not** solve the natural-language front end; it is a contract and audit foundation, with no fabricated language-extraction evaluation.

`transport.py` implements a finite Z/7Z gauge-synchronization diagnostic: exact triangle residual computation, shortest tree and robust edge-disagreement local optimization. Cycles are *not* assumed to contribute independent observations; it is not a novel gauge-theory breakthrough. No scientific superiority claim is allowed until separate matched cycle-message-passing and group-synchronization experiments are preregistered and evaluated.

All frozen V2.1 files and draft PR #40 remain unmodified. A passing test workflow is software verification, not a frontier-intelligence certification.

## Literature context

DreamCoder (Ellis et al., PLDI 2021, DOI `10.1145/3453483.3454080`) already studies compositional library learning; robust group synchronization via cycle-edge message passing (Lerman & Shi, *Foundations of Computational Mathematics*, 2022) already studies cycle-based inference with corrupted relations. NNN must eventually compare its algorithms to these stronger methods, not just toy baselines.
