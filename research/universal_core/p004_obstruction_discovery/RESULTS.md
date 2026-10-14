# NNN P004: Obstruction-driven mechanism discovery, first confirmatory attempt

**Date:** 2026-10-14. **Outcome:** primary superiority claim **not supported**. The deterministic experiment ran once after both commitments were saved to GitHub. No retrospective algorithm patches or test-family specialization were made after scoring.

## Freeze and custody

- Parent branch: `research/nnn-v3-clean-replication-20261014`, at `ad4887d653256e1fcb84e9e8bf72a547af663f49`.
- Isolated branch: `research/p004-obstruction-discovery-20261014`.
- Original August V2.2 draft PR #40 retains SHA `61426a55d096e5e27cc21670e80455aa40482baf`; V2.1 archive retains `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`. Neither was changed.
- Preregistration published before heldout preparation. `experiment.py` SHA-256: `3f44b1eb9209090be49404f0c8b9d6842bfa8b86e6bb9388854d63fed201c412`.
- Private synthetic-label commitment: `5162c16eb18751d4892daf827adf2c4fe9b6b3cabffa7c8608118696e1f3826c`, published in GitHub commit `ba4660a0909804329626d5658ffffa518c0d878a` before query planning.
- Sealed first-attempt predictions: `51459de60a220fc84dbd2cbb416553d840feb1dddc878969a2aebe864fb20b12`, published in GitHub commit `b7c9e987005f6135d0cfb1d8a96638c7d512e104` before target scoring.
- 120 independent generated episodes, each with 4 demonstrations, one intervention reply and five disjoint future targets. Three seed streams (81091/81092/81093), 24 episodes per true cause, 600 scored targets.

## Primary results

| Method | Raw target accuracy | True-cause diagnosis accuracy |
|---|---:|---:|
| Constant-transport baseline | 56.83% | 20.00% |
| Passive Bayesian model selection | 76.33% | 60.83% |
| Random intervention, one query | 87.67% | 77.50% |
| Entropy-maximizing Bayes, one query | 92.00% | 85.00% |
| Bayesian target-risk query | 93.17% | 85.00% |
| ODMD = target risk + finite-field rank bonus | **93.33%** | **85.00%** |
| ODMD without quadratic hypothesis | 77.33% | 65.00% |
| ODMD without switch hypothesis | 87.33% | 74.17% |

ODMD vs **strongest baseline** (target-risk): **+0.1667 percentage points**, equivalent to one additional correct target prediction of 600. Cluster-bootstrap 95% interval: **0 to +0.5 percentage points**. Preregistered success demanded >= +5 percentage points with positive lower CI bound; **gate FAILS**.

ODMD vs passive Bayes: **+17 percentage points**, cluster-bootstrap 95% CI approximately **+12.33 to +22.17 percentage points**. This isolates the **value of receiving one informative observation under an established hypothesis model**, not superiority or mathematical novelty of ODMD.

Per-seed ODMD accuracy: 91.5%, 96.5%, 92.0%. Matching target-risk scores: 91.5%, 96.5%, 91.5%.

Per-cause ODMD accuracy: constant 90.83%, entity 88.33%, switch 95.83%, quadratic 97.50%, path 94.17%. Absence of the quadratic hypothesis crushed its own family accuracy to 16.67%; absence of the switch hypothesis reduced switch accuracy to 51.67%. These are diagnosis-model capacity controls, *not* operator-invention experiments.

## The actual mathematical insight

In a *fixed and correctly specified* hypothesis class with a correctly calibrated posterior and a one-query horizon, the Bayes query that minimizes expected future target loss cannot be improved in expectation using a deterministic extra statistic computed from the same observations. For observed training data D and permitted probe actions a, define posterior predictive decision risk

`R(D) = sum_target min_pred E[ loss(pred,Y_target) | D ] / n_targets`.

The optimal single-step query is `a* = argmin_a E[ R(D plus observed_reply(a)) | D ]`. Any heuristic over the same candidates (including a design-matrix rank bonus) cannot have *strictly lower conditional expected Bayes risk* if the specified posterior is correct. The implementation's `target_risk` planner approximates this ideal with a noiseless query-outcome partition and a small 0.5% post-query contamination model; therefore the theorem applies to the idealized decision problem, **not as a code-correctness guarantee for this approximation**.

This explains the negative result mechanistically. ODMD selected a different probe from target-risk in only **9 of 120** episodes, altered a target prediction in **one episode**, and gained exactly **one correct answer**. The contextual-feature matrix increased rank under the chosen ODMD probe in **116 of 120** episodes. Almost every candidate useful probe already did so, making the rank bonus weak at distinguishing interventions.

**Eureka-level research direction, not breakthrough proof:** Focus ODMD on **hypothesis-space revision** (new state variables, semantic scope distinctions and executable operators) when existing models fail posterior predictive checks. Better query ranking inside the existing five candidate families is mathematically the wrong target. The next experiment should withhold entire algorithmic families from the *object* DSL, permit bounded metalanguage invention, penalize complexity and require prospective transfer. Compare against direct metalanguage search and modern robust inference at equal compute.

## Limitations and reproducibility

The generator encodes five predefined explanations in a finite field; this is neither a natural-language semantic benchmark nor independent proof of a previously unexpressible operation. Generated heldout cases share templates with development and the code was readable: labels were *procedurally sealed* by hash, not independently hidden from an external evaluator. One query is noiseless while passive demonstrations are corrupted at defined rates; this controlled intervention makes query-based methods significantly stronger, and may be optimistic relative to real sensors. The one-step `target_risk` objective is approximate. There was no actual CEMP/DESC implementation in this pilot. These limitations preclude a generalization or frontier claim.

Run `python -m unittest discover -s tests -v` and `python audit.py evidence/holdout`. The complete scored dataset, responses, prediction seal, original score and source are available in the separate downloadable reproducibility archive. A GitHub Actions regression run, if successful, independently verifies code and frozen commitments, **not** fresh blind generalization.
