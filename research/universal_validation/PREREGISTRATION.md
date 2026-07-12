# Universal Validation Program — Preregistration

Frozen before implementation on this branch.

## Scientific question

Does the hybrid world-to-graph-to-reasoning architecture generalize beyond BBH task engineering into harder, unfamiliar, paraphrased, document-grounded, cross-domain and independently reproducible settings?

## Claim policy

No result may be described as universal intelligence. The strongest permitted claim is determined by the weakest completed lane below. Missing predictions and abstentions count as incorrect unless a selective-risk metric is reported separately.

## Lane A — Unsaturated reasoning

**Primary benchmark:** official full BIG-Bench Extra Hard (BBEH), 4,520 examples.

Primary metric: the official evaluator and harmonic aggregate. Secondary metrics: macro accuracy, micro accuracy, task coverage, selective accuracy, failure taxonomy and task-level scores.

No BBEH answer labels may be used to alter a solver after the branch is frozen. Development is permitted only on official demonstrations/training material where provided. Any post-score repair must be reported as a separate adaptive result and cannot replace the frozen score.

## Lane B — Unfamiliar, contamination-resistant tasks

Preregistered benchmarks:

1. A frozen current snapshot of the official LiveBench reasoning subset.
2. CLUTRR held-out systematic-generalization splits `gen_train23_test2to10` and `gen_train234_test2to10` as an already independent algebraic test.
3. One repository-level executable reasoning benchmark if the public evaluator is runnable without proprietary data; otherwise this slot is reported unavailable rather than substituted post hoc.

## Lane C — Adversarial paraphrase and metamorphic robustness

For every exact-cell task with machine-verifiable semantics, generate deterministic transformations:

- entity renaming;
- option permutation;
- irrelevant-but-noncontradictory sentence insertion;
- whitespace/punctuation changes;
- relation inversion plus argument reversal;
- clause-order permutation;
- numeric/date surface-form changes where semantics are preserved.

Primary metric: prediction invariance and proof invariance. Any transformed item whose semantics cannot be mechanically certified is excluded before prediction.

Pass threshold: >=99% invariance on accepted exact-cell transformations and no statistically significant degradation above 0.5 percentage points.

## Lane D — Real document grounding

Frozen public datasets:

- legal: ContractNLI and LegalBench task subsets with evidence-bearing text;
- finance: FinQA or TAT-QA, selected by public evaluator availability;
- scientific/biomedical: PubMedQA or SciFact, selected by public evaluator availability;
- tables/evidence: TabFact and FEVER/FEVEROUS where runnable.

Report extraction quality separately from reasoning quality. End-to-end correctness must not be inferred from oracle-graph performance.

## Lane E — Cross-domain transfer

Evaluate reasoning cells outside the domain that motivated them:

- order/constraint cell: BBH ordering -> BBEH spatial/time/order analogues;
- theorem/SAT cell: formal fallacies -> rule-based document reasoning;
- table cell: synthetic/penguin tables -> TabFact/FinQA tables;
- partial algebra cell: CLUTRR kinship -> at least one non-kinship finite-relation task if available.

No target-test labels may tune the shared cell.

## Lane F — Cost and latency

Measure on the same hardware/run:

- exact-cell wall time, CPU time and peak memory;
- semantic-jury API latency and token counts;
- router overhead;
- end-to-end latency distribution;
- estimated model-only versus hybrid cost under a frozen public price sheet.

Report median, p95, throughput and cost per 1,000 tasks. Cached calls are excluded from latency but reported separately.

## Lane G — Independent replication

Requirements:

- pinned source commit;
- SHA-256 hashes of code and datasets;
- one-command runner;
- no hidden local files;
- artifacts containing raw predictions, errors and environment metadata;
- a second clean runner in a separate repository or compute environment.

A result is "replicated" only when the second runner independently regenerates the reported aggregate from the pinned inputs.

## Decision gates

- **Research prototype:** Lane A completed with transparent failures.
- **Broad reasoning architecture:** Lanes A–C pass.
- **Cross-domain reasoning system:** Lanes A–E pass with nontrivial end-to-end document results.
- **Deployment candidate:** Lanes A–G pass plus domain-specific safety and human review.
- **Universal intelligence:** not inferable from this program, regardless of score.
