# NNN Universal Reasoning Compiler: Causal Holonomy Pilot 001

**Registered 2026-10-14.** Status: protocol defined prior to opening held-out labels. This is a *synthetic mechanistic negative-control experiment*, not a claim of ARC generalization or a reproduction of the existing Universal Core engine. Original baseline: `61426a55d096e5e27cc21670e80455aa40482baf`; V2.1 frozen SHA: `1d7c489bcdbff755d638b35ad47ce62bd4fe829d`.

## Question and identification

Under identical oracle-graph observations, path candidates and budgets, does closed-path holonomy consistency select a more accurate unknown affine transport between two vertices than simpler alternatives when queried on graph configurations and **composition lengths withheld from supervised development**? Null: the holonomy score does not outperform the best feasible matched non-holonomy baseline. In this setting, there is a stronger *algebraic equivalence null*: exact loop closure (`T_j^-1 o T_i = identity`) is the same equality predicate as `T_i = T_j`; with identical candidate paths, holonomy scoring and plurality/DSL scoring must agree, absent implementation faults.

This pilot is deliberately capable of producing a negative result. It does **not** test the ability to invent a new operator or parse natural-language semantics, both of which remain open problems.

## Data and separation

Group: invertible affine transformations on `Z/11Z`, `x -> ax+b (mod 11)`, `a != 0`. Each graph has hidden node gauges; the correct transport from `s` to `t` is `g_t o g_s^-1`. Observed edges are exact or have independently corrupted coefficients; all methods see **the same observed edges**. The edge grammar (110 maps) is fixed before evaluation.

- Development: three independent streams (`8101`, `8102`, `8103`), 140 graphs/stream, eight vertices, query shortest graph distance <=2, 50:50 noiseless versus 15% edge corruption.
- Holdout: 100 fresh graphs/stream, thirteen vertices and unseen graph layout parameters, query shortest graph distance >=4, 50:50 noiseless versus 15% corruption. Vertex IDs are independently randomized 40-bit strings. Task instances and graph gauges are generated from disjoint seed offsets; no ARC or external benchmark labels are touched.
- The implementation is frozen by SHA-256 in `commitments.json`. `prepare` writes public train/holdout inputs and independently SHA-256-committed `sealed_labels.json`. `predict` **never opens** the sealed labels; it saves every method's first predictions in a separate JSON. `score` verifies both commitments and reads labels only after predictions are sealed. The scoring file refuses overwrite. One evaluation only, with no repair after held-out scoring.
- Synthetic generator and public train-case labels are visible during development, so the boundary is **unseen generated instances/structures**, not independent real-world holdout collection. It is a mechanistic diagnostic only.

## Methods and parity

All solvers use identical oracle-typed edge graph, inferred path set (BFS-enumerated simple paths, max 32 paths and 7 hops), modulus, candidate affine maps and exact-match objective. One test query per graph. Methods:

1. **Holonomy**: compose transports along each candidate path and maximize the number of exact identity loop residuals against all other paths; abstain on top-score ties.
2. **Discrete DSL enumerator**: choose the affine program fitting the most *identical path-derived* demonstrations at probe inputs `x=0,1`; abstain on ties. Algebraically a strong non-holonomy competitor.
3. **Graph search without holonomy**: deterministic first shortest path.
4. **Learned program ranker**: 3-feature supervised softmax candidate ranker trained on development labels only (40 epochs, fixed step, no holdout tuning); shares candidate set. This is a modest learned synthesizer, not an LLM-scale synthesizer.
5. **Remove composition**: answer only from a direct edge; abstain otherwise.
6. **Random/noisy transport**: perturb 20% of composed path translations with a per-task deterministic random generator, then apply the loop scorer. This intentionally changes measurement quality and is not a capacity-matched competing architecture.

The comparison matches candidate path enumeration and available data, **not** arithmetic cost: holonomy checks up to distinct-candidate count times path count group residuals; DSL checks two probe values per comparison; learned model uses supervised training. Runtime and operations must be reported. An oracle-versus-inferred-semantic-graph ablation is expressly **deferred**, since doing it without an actual input parser would manufacture an advantage.

## Metrics, significance and stopping

Each method: raw exact-program accuracy over all heldout cases, coverage, wrong accepted, selective accuracy, 95% Wilson interval for raw accuracy, per-noise-regime scores, Brier score using candidate-support fraction as a non-calibrated confidence proxy, risk at 25/50/75/100% ranked coverage, median per-query latency and mean operation count. Paired holonomy-versus-each-baseline discordance and exact two-sided binomial McNemar p-value. For holonomy against the **best** other method, 4,000 paired bootstrap resamples with fixed seed `700700`, 95% percentile interval, and per-stream effects. Report ties, abstentions and null results explicitly.

**Primary superiority gate fixed before scoring**: holonomy improves raw exact accuracy by at least 5.0 percentage points over the strongest non-holonomy comparator, the paired-bootstrap lower 95% endpoint exceeds zero, and every seed stream has nonnegative difference. A passed gate would support only **this synthetic composition domain** and requires a second independent replication before any broader claim. A failed gate means no demonstrated holonomy-specific advantage here; do not patch the method using held-out failure examples or turn the synthetic holdout into a tuning corpus.

## Separate semantic front-end track

Unsolved. Next prerequisite: independently evaluate entity, relation, operator, quantifier/negation, time/unit and evidence-provenance graph extraction on real unseen source documents; use typed-graph exact match and downstream delta when substituting a predicted graph for an oracle graph. The current pilot uses oracle graph input only. An actual front-end must be compared to a basic structured-extraction baseline before making end-to-end reasoning claims.

## Reproduction

With Python 3.10+ and no external dependencies:

```bash
python -m unittest discover -s tests -v
python experiment.py prepare --out evidence/pilot-001
python experiment.py predict --out evidence/pilot-001
# Commit/seal prediction bytes before unsealing:
sha256sum evidence/pilot-001/predictions.json
python experiment.py score --out evidence/pilot-001
sha256sum evidence/pilot-001/*
```

The script intentionally refuses reruns in the same output path after prediction/scoring. For reproducibility without touching the original holdout, run in a different new directory. Hashes and environment details are recorded in the final evidence manifest.