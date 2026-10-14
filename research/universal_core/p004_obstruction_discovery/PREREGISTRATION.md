# P004 preregistration: causal explanation of modular transport obstructions

**Protocol 0.1, frozen before opening confirmatory labels.** 2026-10-14. The research-only branch must not change frozen V2.1, ARC grammar, or draft PR #40.

## Claim under test

Can a **rank-aware, outcome-driven intervention policy** (ODMD) improve prospective predictions and correctly distinguish the cause of apparent modular-transport inconsistencies over strong Bayesian baselines using **the same predefined hypothesis library** and identical evidence budgets? No claim of novel operator invention follows even if the answer is yes.

H0: ODMD provides no positive paired prospective accuracy improvement relative to the best of passive Bayes, uniformly random query, entropy-maximizing Bayesian query, and target-risk-maximizing Bayesian query.

H1: ODMD has >= 5 percentage points higher raw test accuracy than the strongest such baseline, with episode-clustered 95% bootstrap CI strictly above zero, across 3 heldout seeds. Diagnosis accuracy, macro accuracy, search cost, and class-specific failures are secondary metrics. No post-hoc change to the primary threshold.

## Generative task / identifiability

Prime group Z_13. Five **frozen and known** explanation families:
- `constant`: ordinary x+a, with higher independent recording corruption;
- `entity`: x+a+b*entity (incorrectly merged semantic entities);
- `switch`: x+a+b*switch (unobserved controllable mode, causal action setting);
- `quadratic`: x+a+b*x^2 (object DSL lacks this, but it is explicitly available to this experiment's hypothesis library);
- `path`: x+a+b*path (genuine route dependence).

All non-constant b are nonzero; coefficients and nominal observations are randomized and never passed to the inference module. The three binary observable/control features are strongly confounded in passive demonstrations. No category tokens are exposed in public cases. Intervention inputs can independently vary the three bits, and the query output is a physically plausible observed response. Each task allows exactly *one* query. All scored target inputs are outside the range of training inputs and not included in query pool (tests x=9..12, queries x=0..8). This is procedural synthetic withholding, not a third-party blind benchmark or family-level holdout of unseen operators.

## Fixed methods and budgets

`flat` (robust constant group transport), `passive` (exact Bayesian model averaging without querying), `random` (same Bayesian posterior, one random intervention), `entropy` (maximize entropy of predicted intervention outcome), `target_risk` (minimize expected Bayes 0-1 predictive risk on the visible target inputs), `odmd` (same target-risk score plus a fixed bonus of 0.04 for one-step increase in GF(13) design-matrix rank), and two distinct ablations removing quadratic and switch model families. Each policy receives the same training examples, candidate hypothesis family, query pool, and at most one query, except explicitly described capacity reductions. Bayesian posterior enumerates all family and coefficient variants under frozen noise rates; no fitted weights or post-reveal changes. We count 36 evaluated query options per query-capable episode, with 5 future target predictions. The plain Bayes `target_risk` comparator is an intentionally strong baseline.

## Data partitions

Development: 3 streams, 12 tasks per stream, 5 demonstrations and x drawn 0..4, known labels for debugging *only*. Confirmatory: independent seed streams 81091, 81092, 81093; 40 tasks per stream, 4 training demonstrations and x drawn 0..3. The 120 confirmatory episodes are evenly balanced across the five cause categories, 600 scored target rows. These are not canonical-equivalent families; they do share generator templates and must not be represented as truly novel mechanism families. The generator is deterministic for audit; hidden labels are committed by SHA-256 before any confirmatory query-selection or prediction. `plan` and `predict` do not load target answers or mechanism labels; the oracle broker can release only selected intervention answers. Final score is generated once after prediction hash sealed.

## Reporting and stop conditions

Report unconditional exact accuracy, diagnostic class accuracy, per-cause performance, abstention (none), case-clustered paired bootstrap CI, three seed effects, and compute budget. Require an additional independent generator design and external robust synchronization comparators (CEMP/DESC/IRLS) before any claim beyond this toy probe. If ODMD cannot beat **target_risk** (or the strongest other baseline), report negative evidence and revise theory only for the *next* preregistered experiment. No reevaluation on revealed suite.

## Structural mathematical checkpoint

Design rank over GF(13) is a *necessary feature-identifiability diagnostic*, not a sufficient causal identification theorem. Cycle inconsistencies could arise from multiple observationally equivalent mechanisms. Since both ODMD and Bayes can use identical observation features, the presence of rank structure may not provide an advantage over optimal Bayesian target-risk querying. This is deliberately falsifiable.

## Development checkpoint, explicitly not confirmatory evidence

A separate 36-episode development-only run yielded 97.22% prospective exact accuracy for both ODMD and Bayesian target-risk, with identical aggregate predictions in that trial. This observation motivates a *future* experiment about model-class expansion, but the P004 protocol, ODMD formula, holdout seeds and superiority threshold are **unchanged** before the first confirmatory run. Under a correctly specified Bayesian decision model, the posterior-target-risk criterion already maximizes expected single-query predictive utility; a rank heuristic with the same hypothesis set generally has no fundamental advantage. The confirmatory test remains useful as an adversarial null check. Do not claim a win from outperforming weaker baselines.
