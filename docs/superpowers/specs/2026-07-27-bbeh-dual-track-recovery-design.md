# BBEH Dual-Track Recovery and 100% Fit Design

**Date:** 2026-07-27  
**Repository:** `Chrisbryan17/MLE-agent`  
**Branch:** `universal-structured-residual-v1`  
**Benchmark pin:** `80d12ca916b7158f22293fcf3144f4d3d854d4be`

## 1. Objective

Recover the two missing structured-residual routes, BoardgameQA and Geometric Shapes, restore the historical six-task structured result as a GitHub-reproducible artifact, and then improve the complete BBEH result through two rigorously separated lanes:

- **Track G — General compiler:** a reusable reasoning implementation without row-specific benchmark memorization.
- **Track F — Public-corpus fit:** an explicitly benchmark-specific residual layer permitted to use public-row signatures and exceptions.

The program ultimately targets a fitted public-corpus score of **4,520/4,520**, while preserving every general-lane score independently and never representing Track F as unseen-test performance.

## 2. Claims Boundary

All work uses the pinned public BBEH corpus and is adaptive benchmark development. Therefore:

1. Track G scores measure performance of a reusable compiler on the public corpus after development, not blind generalization.
2. Track F scores measure corpus fitting only.
3. Exceptions and abstentions count as wrong unless a separately named typed-equivalence metric is reported.
4. First-score artifacts remain immutable. Target-informed revisions receive a new version and new seals.
5. No fitted result may replace, overwrite, or be merged into the corresponding general result.

## 3. Existing Baseline

The repository-backed checkpoint currently contains:

- Exact-v4 core: 1,999/2,000.
- Zebra v3: 200/200.
- Buggy Tables v1: 200/200.
- Object Properties v1: 200/200.
- Time Arithmetic v1: 199/200 strict and 200/200 typed temporal equivalence.
- BoardgameQA pinned task and structured-source export workflows.

The conservative repository-backed full-BBEH floor is 3,168/4,520 strict. The prior isolated structured closeout reported 1,200/1,200 adaptive and 1,195/1,200 strict, but BoardgameQA and Geometric Shapes source must be reconstructed before that result is repository-reproducible.

## 4. Scope Decomposition

Implementation is divided into independently testable milestones:

1. **BoardgameQA Track G compiler and evidence.**
2. **BoardgameQA Track F residual fit layer.**
3. **Geometric Shapes Track G compiler and evidence.**
4. **Geometric Shapes Track F residual fit layer.**
5. **GitHub-backed six-task structured closeout.**
6. **Seven-task semantic residual improvement.**
7. **Full 4,520-row dual-track aggregation.**

The first implementation plan covers milestones 1–5. Semantic improvement and full 100% fitting receive separate plans after the structured closeout is sealed.

## 5. Track G Architecture

### 5.1 Shared protocol layer

A shared evidence harness will:

- load the pinned task file;
- perform input-only grammar or schema audit;
- generate predictions without reading targets;
- write canonical JSON bytes;
- seal predictions with SHA-256;
- score only after verifying the seal;
- preserve the first score;
- write mismatches, latency, coverage, and source hashes;
- fail CI on unhandled exceptions, seal mismatches, row-count mismatches, or input-hash mismatches.

### 5.2 BoardgameQA compiler

BoardgameQA will use a typed defeasible-logic pipeline rather than direct label prediction.

#### Data model

- `Literal(subject, predicate, object, polarity)`
- `Variable(name)`
- `Fact(literal)`
- `Antecedent(kind, literals, quantifier)`
- `Rule(rule_id, antecedents, consequent)`
- `Preference(stronger_rule_id, weaker_rule_id)`
- `Theory(facts, rules, preferences, query)`
- `Derivation(literal, supporting_rules, defeated_rules)`

#### Parsing

The compiler first consumes the structured source representation where available. A separate alignment layer maps each BBEH English prompt to a structured source theory using normalized facts, goals, rules, preferences, and source-text signatures.

The parser must support:

- positive and explicitly negated facts;
- unary and relational predicates;
- variables and constants;
- conjunctions;
- existential antecedents;
- pronoun and possessive binding;
- relative-clause consequents;
- parenthetical clauses;
- declared rule-preference relations;
- query polarity.

#### Inference

The proof engine uses target-directed search:

1. Search for derivations of the query.
2. Search for derivations of its explicit negation.
3. Apply substitutions and existential witnesses.
4. Evaluate applicable rules against the factual world.
5. Resolve opposing conclusions using the declared preference graph.
6. Return `True`, `False`, or `Unknown` according to the task label mapping.

Cycles are handled by memoized proof states with an explicit `in_progress` marker. A cyclic branch without independent factual support does not establish a literal.

#### General-lane restrictions

Track G must not reference:

- benchmark row indices;
- input SHA-256 values for answer selection;
- target labels during generation;
- hard-coded per-row outputs;
- lookup tables whose keys uniquely identify public examples.

Input hashes are permitted only in the evidence harness to verify row identity after predictions are generated.

### 5.3 Geometric Shapes compiler

The compiler will reconstruct the task as a typed spatial program:

- parse entities, shape attributes, transformations, and relations;
- normalize aliases and orientation descriptions;
- build a scene graph;
- apply deterministic transformations in order;
- answer the requested property from final graph state.

The general lane may contain reusable grammar families and geometric operators, but no row-specific output map.

## 6. Track F Architecture

Track F runs only after the corresponding Track G first score is sealed.

Each fitted adapter has a strict boundary:

```text
public prompt -> Track G prediction -> fitted residual lookup/rule -> Track F prediction
```

Permitted mechanisms include:

- exact normalized-input signatures;
- input SHA-256 keyed corrections;
- row-specific exception rules;
- public-corpus source mappings;
- direct output lookup for unresolved rows.

Every fitted correction must record:

- task name;
- row index;
- input hash;
- Track G prediction;
- fitted prediction;
- correction reason;
- mechanism type.

Track F code, tests, output directories, prediction seals, and score files remain separate from Track G.

## 7. Source Alignment Strategy for BoardgameQA

The exported structured source is the primary reconstruction asset. Alignment proceeds without labels:

1. Canonicalize each BBEH prompt by whitespace, punctuation, quote, and Unicode normalization.
2. Canonicalize source natural-language fields using the same procedure.
3. Attempt exact canonical text matching.
4. Attempt component matching over facts, query, rule sentences, and preference sentences.
5. Use deterministic token fingerprints for reordered but equivalent source text.
6. Reject ambiguous matches rather than selecting arbitrarily.
7. Produce an alignment audit containing matched, unmatched, and ambiguous counts.

The acceptance gate for Track G scoring is 200/200 uniquely aligned prompts or a complete native prompt parser that removes the need for source alignment.

## 8. Testing Strategy

All implementation follows red-green-refactor.

### 8.1 Unit tests

BoardgameQA tests cover:

- explicit negation;
- conjunction;
- variable substitution;
- existential antecedents;
- contradictory conclusions;
- transitive preference chains;
- cyclic rule dependencies;
- parenthetical consequent subjects;
- relative-clause variable binding;
- possessive phrases such as `her cards`;
- generic noun phrases such as `a weapon`;
- phrases such as `something ... secret`;
- unknown when neither polarity is supported.

Geometric Shapes tests cover:

- alias normalization;
- rotation and reflection;
- relative position composition;
- attribute mutation;
- operation ordering;
- unknown or malformed scene handling.

### 8.2 Metamorphic tests

The general compilers must preserve answers under transformations that do not change semantics, including:

- harmless whitespace and punctuation changes;
- consistent entity renaming;
- reordering independent facts;
- reordering rules when preferences are unchanged;
- equivalent explicit-negation syntax;
- equivalent geometric aliases.

### 8.3 Corpus audits

Before scoring:

- all 200 inputs must parse or align;
- every rule and preference must compile;
- no target field may be accessed by prediction-generation code;
- all generated rows must have stable input hashes;
- prediction files must be byte-sealed.

### 8.4 Regression tests

Every discovered general failure receives a minimal grammar or derivation regression test before a fix. Every Track F correction receives a fitted-lane test proving that Track G remains unchanged.

## 9. Evidence and Directory Layout

Proposed source files:

```text
research/universal_validation/
  bbeh_evidence_protocol.py
  bbeh_boardgame_ir.py
  bbeh_boardgame_parser.py
  bbeh_boardgame_inference.py
  bbeh_boardgame_alignment.py
  bbeh_boardgame_general_v1.py
  bbeh_boardgame_fit_v1.py
  bbeh_geometric_general_v1.py
  bbeh_geometric_fit_v1.py
  bbeh_structured_six_task_closeout_v2.py
```

Proposed tests:

```text
research/universal_validation/
  test_bbeh_evidence_protocol.py
  test_bbeh_boardgame_ir.py
  test_bbeh_boardgame_parser.py
  test_bbeh_boardgame_inference.py
  test_bbeh_boardgame_alignment.py
  test_bbeh_boardgame_general_v1.py
  test_bbeh_boardgame_fit_v1.py
  test_bbeh_geometric_general_v1.py
  test_bbeh_geometric_fit_v1.py
  test_bbeh_structured_six_task_closeout_v2.py
```

Artifact layout:

```text
artifacts/
  boardgame_general_v1/
  boardgame_fit_v1/
  geometric_general_v1/
  geometric_fit_v1/
  structured_six_task_closeout_v2/
```

Each artifact directory includes:

- `grammar_audit.json` or `alignment_audit.json`;
- `predictions.json`;
- `predictions.sha256`;
- `first_score.json`;
- `mismatches.json`;
- `results.json`;
- `SHA256.json`.

## 10. CI Design

A new GitHub Actions workflow will:

1. check out the exact PR head, not the generated merge ref;
2. clone BBEH at the pinned commit;
3. fetch or reconstruct the exported BoardgameQA source bundle;
4. run focused unit and metamorphic tests;
5. run Track G corpus audits;
6. generate and seal Track G predictions;
7. score Track G once;
8. generate and seal Track F predictions;
9. score Track F;
10. run the six-task closeout;
11. recompute every listed SHA-256;
12. upload one immutable combined artifact.

CI fails when any expected row is absent, any source pin differs, any seal fails, any Track F dependency contaminates Track G imports, or any historical first-score file changes.

## 11. Acceptance Gates

### BoardgameQA Track G

- 200/200 inputs uniquely aligned or natively parsed.
- Zero uncompiled rules or preferences.
- Zero generation exceptions.
- 100% coverage.
- First score sealed and preserved.
- No prohibited benchmark identifiers in answer-selection code.

### BoardgameQA Track F

- 200/200 strict exact accuracy.
- Every correction represented in the fitted correction ledger.
- Track G source and prediction hash unchanged.

### Geometric Shapes Track G

- 200/200 inputs parsed.
- Zero generation exceptions.
- 100% coverage.
- First score sealed and preserved.

### Geometric Shapes Track F

- 200/200 strict exact accuracy.
- Track G source and prediction hash unchanged.

### Six-task structured closeout

- One GitHub Actions artifact covering all 1,200 rows.
- Track F total: 1,200/1,200 strict exact.
- Track G total reported separately.
- Per-task scores, micro, macro, and harmonic values included.
- All source, corpus, prediction, score, and manifest hashes verified.

## 12. Failure Handling

- Parsing failures become explicit audit failures, not silent abstentions.
- Ambiguous source alignments block scoring until resolved by a general deterministic discriminator.
- Contradictory undefeated derivations return `Unknown` unless task semantics specify another result.
- Any target access during prediction generation is a protocol violation and invalidates that artifact.
- After three failed fixes within one component, implementation pauses for architectural review rather than accumulating exceptions.

## 13. Post-Structured Roadmap

After the six-task closeout succeeds:

1. repair the semantic jury workflow without altering historical sealed scores;
2. build per-task semantic Track G adapters;
3. add separately labeled Track F residual maps;
4. aggregate all 4,520 examples under the dual-track protocol;
5. drive Track F toward 4,520/4,520;
6. evaluate Track G on newly generated or held-out structurally equivalent data to estimate actual generalization.

## 14. Definition of Done

This design is complete when the repository contains a reproducible, hash-sealed six-task structured workflow whose general and fitted lanes are independently inspectable, BoardgameQA and Geometric Shapes are restored from committed source, fitted structured accuracy is 1,200/1,200, and no benchmark-specific mechanism can affect a Track G prediction.