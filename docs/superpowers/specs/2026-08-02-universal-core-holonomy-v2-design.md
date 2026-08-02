# Universal Core Holonomy V2 Design

Date: 2026-08-02  
Status: approved by standing instruction  
Base commit: `0194001e82721cd9081aca16bb1c04f34d1c56aa`

## 1. Purpose

Universal Core V1 showed a sharp boundary in the first externally separated blind run:

- 300 of 600 rows correct.
- 300 attempted rows correct.
- 300 abstentions.
- Level 4: 0 of 200 at zero coverage.

The failure pattern shows that V1 can identify and compose a limited catalog of known transforms, but cannot yet derive a new task algebra from demonstrations. V2 replaces fixed-template induction as the primary mechanism with a holonomy-native program learner.

Run 001 is regression material only. Any capability claim for V2 must come from a fresh challenge created after the V2 code and protocol identities are frozen.

## 2. Claims boundary

V2 may be described as holonomy-native only when the executable path includes all of the following:

1. typed fibers for task states and schemas;
2. learned local transports between fibers;
3. explicit path composition;
4. explicit closed-loop generation;
5. residual computation on each closed path;
6. residual-driven candidate rejection and ranking;
7. grammar growth beyond a fixed one-step catalog.

Passing Run 001 regression is not evidence of new-family generalization. A fresh sealed suite is mandatory.

No report may claim unrestricted universal reasoning. Reports must state the suite composition, row counts, coverage, abstentions, first-attempt accuracy, and the exact code identity.

## 3. Preservation boundary

V2 is additive.

The following identities remain unchanged:

- Universal Core V1: `89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9`
- Blind protocol V1: `0194001e82721cd9081aca16bb1c04f34d1c56aa`
- Run 001 public record: branch `blind-eval-run-001-public`
- Run 001 first-attempt artifact: `8835109636`

V2 code lives under:

`research/universal_core/holonomy_v2/`

V2 tests live under:

`research/universal_core/holonomy_v2/tests/`

Run 001 regression fixtures live under test-only paths and may not be imported by production modules.

## 4. Design principles

### 4.1 Typed search, not arbitrary code

The engine searches a closed typed grammar. It does not emit or execute arbitrary Python. Every program node has declared input and output types, deterministic semantics, a canonical form, a complexity cost, and bounded runtime.

### 4.2 Data-derived atoms

The grammar begins with generic combinators and derives task atoms from demonstrations and instructions:

- field paths;
- literal constants;
- comparison relations;
- label maps;
- symbol tables;
- graph endpoints;
- state fields;
- action names;
- ordering keys;
- resource capacities;
- precedence relations.

Production code may not contain benchmark row hashes, task identifiers, hidden targets, or Run 001 family names.

### 4.3 Holonomy as an executable gate

A candidate program is not accepted merely because it replays demonstrations. It must also pass closed-path checks.

For a path `gamma = e_n ... e_1`, define:

`H_gamma = T_e_n o ... o T_e_1`

For a closed path based at state `x`, define residual:

`r_gamma = distance(H_gamma(x), x)`

Exact fibers use canonical equality. Numeric fibers use exact rational arithmetic when possible and a predeclared tolerance otherwise. Structured fibers use schema-aware canonical distance.

A candidate with a nonzero mandatory residual is rejected. Optional residuals contribute to ranking.

### 4.4 Conservative first-attempt behavior

The engine may abstain when no candidate passes all mandatory gates. Coverage growth is important, but incorrect high-confidence output is worse than a typed abstention.

### 4.5 Two reported tiers

Tier D is deterministic and local.

Tier H adds an external model proposer. The proposer may return only typed grammar programs and rationale metadata. It cannot execute hidden rows, inspect targets, bypass verification, or alter scoring.

Tier D and Tier H are scored and reported separately.

## 5. Architecture

### 5.1 Fiber model

`fibers.py` defines:

- `FiberType`
- `FiberSchema`
- `FiberValue`
- `FiberMap`
- `Observation`
- `TransportSignature`

Fibers represent scalar, sequence, record, table, graph, state, action, label, and constraint domains.

Schemas are structural and do not retain inert metadata.

### 5.2 Typed program graph

`program.py` defines an immutable expression DAG.

Required node families:

- input;
- literal;
- field;
- index;
- compose;
- map;
- filter;
- project;
- order;
- aggregate;
- compare;
- boolean combination;
- conditional;
- label map;
- graph query;
- finite-state step;
- repeated step;
- priority rule;
- bounded search;
- output formatting.

Each node provides:

- type checking;
- canonical serialization;
- deterministic execution;
- complexity cost;
- dependency set;
- optional inverse or partial inverse;
- mutation hooks for verification.

### 5.3 Grammar

`grammar.py` builds the task-specific typed grammar from generic combinators plus data-derived atoms.

The grammar must support:

- multi-step pipelines of bounded depth;
- branching;
- finite-state transition tables;
- defeasible priority rules;
- bounded scheduling and assignment;
- symbol systems with phase or context;
- graph result mapping;
- sequence transforms followed by projection.

Search limits are explicit in configuration and evidence.

### 5.4 Connection graph

`connection.py` creates a graph whose vertices are typed intermediate fibers and whose edges are candidate transports.

Edges come from:

- grammar primitives;
- derived field adapters;
- inverse adapters;
- candidate subprograms;
- observed input-output correspondences.

The graph records provenance from demonstrations and instruction spans.

### 5.5 Closed-path builder

`loops.py` creates mandatory and optional loops.

Mandatory loops include:

- demonstration replay;
- direct path versus decomposed path;
- adapter followed by inverse adapter where defined;
- alpha-renaming round trip;
- record-key permutation round trip;
- row-order permutation for order-insensitive stages;
- state-cycle return checks;
- equivalent rule-order paths when priority semantics require agreement.

Optional loops include:

- leave-one-out reconstruction;
- instruction paraphrase invariants;
- bounded input mutations;
- alternate candidate path agreement.

### 5.6 Residual engine

`residuals.py` computes:

- exact residual;
- numeric residual;
- structural residual;
- label residual;
- constraint violation count;
- path disagreement residual.

It returns a typed `ResidualReport` with per-loop evidence, aggregate mandatory status, optional score, and canonical digest.

### 5.7 Search engine

`search.py` performs cost-guided typed search.

Recommended order:

1. derive atoms;
2. build depth-one candidates;
3. cache typed intermediate outputs on demonstrations;
4. grow candidates by type-compatible composition;
5. prune by partial replay;
6. prune by mandatory residuals;
7. deduplicate by canonical behavior and program digest;
8. run full verification;
9. rank by residual evidence, simplicity, stability, and runtime.

The engine uses deterministic tie-breaking.

### 5.8 Counterexample-guided refinement

`refine.py` derives counterexamples from failed loops and mutations.

A counterexample may:

- add a missing type constraint;
- split an overloaded symbol by context;
- introduce a state variable;
- require a priority relation;
- add a composition boundary;
- reject an invalid inverse;
- require a bounded search node.

Refinement changes the task grammar, not global production code.

### 5.9 Instruction parser

`instructions.py` extracts weak structural hints without making them authoritative.

Hints include:

- comparison phrases;
- ordering direction;
- tie-breaking;
- phase changes;
- priority and exception terms;
- state update verbs;
- resource and capacity terms;
- output-label definitions.

Demonstration and loop evidence remain the final authority.

### 5.10 Model proposer tier

`proposer.py` defines a provider-neutral interface.

Inputs:

- instructions;
- demonstrations;
- output schema;
- allowed grammar;
- bounded search context.

Outputs:

- typed program data;
- claimed intermediate types;
- rationale;
- confidence metadata.

Every proposal is parsed into the same immutable program graph and passes the same gates as deterministic candidates.

### 5.11 Engine

`engine.py` exposes:

- `induce_deterministic`
- `induce_with_proposer`
- `predict`
- `abstain`
- `evidence`

Hidden inputs are not used during induction or candidate ranking.

## 6. Run 001 regression program

Run 001 targets and evaluator code are now public and may be used under test-only paths.

The regression program must include:

- the original 12 packages;
- randomized task identifiers;
- renamed fields;
- changed constants;
- changed symbol alphabets;
- changed labels;
- changed graph node names;
- changed board dimensions where valid;
- changed capacities and durations;
- demonstration reorderings;
- fresh rows generated from the revealed family rules.

A production import scan rejects any import from regression generators or fixtures.

The minimum V2 regression gate is:

- original Run 001: at least 600 of 600 attempted and correct;
- mutated Run 001 families: at least 95 percent raw accuracy at at least 95 percent coverage;
- zero row-key lookup findings;
- deterministic replay;
- all mandatory holonomy loops pass for accepted candidates.

This gate is engineering regression only.

## 7. Fresh evaluation program

### 7.1 Run 002

After a V2 code freeze, create a new evaluator outside the repository.

Run 002 must contain:

- at least 16 families;
- at least 800 hidden rows;
- at least 6 genuinely new rule systems;
- balanced demonstration budgets;
- renamed schemas and terminology;
- adversarial ambiguity cases;
- no generator reuse from V1, V2 regression, or Run 001.

### 7.2 Reporting

Report Tier D and Tier H separately.

The primary metric is:

`new-system first-attempt raw accuracy at observed coverage`

Also report:

- overall raw accuracy;
- attempted accuracy;
- coverage;
- abstentions;
- task macro-average;
- per-family results;
- confidence intervals;
- runtime and search budget;
- residual counts;
- code and artifact digests.

### 7.3 Iteration rule

After each fresh run:

1. freeze and retain the exact attempt;
2. publish the complete result;
3. move that suite into regression status;
4. change the engine only after reveal;
5. create the next fresh suite after the new code freeze.

No suite may serve as both development data and fresh evidence for the same code identity.

## 8. Security and anti-cheating

Production scans reject:

- dynamic Python evaluation;
- hidden-target fields;
- target ledgers;
- row-hash answer maps;
- task-id routing;
- regression-fixture imports;
- network access in deterministic execution;
- writes outside the attempt directory;
- unbounded loops;
- arbitrary imports in generated programs.

Every attempt records source identity, dependency versions, configuration, grammar limits, program digests, residual digests, prediction digests, and manifests.

## 9. Error handling

Typed failures include:

- `TYPE_MISMATCH`
- `GRAMMAR_EXHAUSTED`
- `SEARCH_BUDGET_EXCEEDED`
- `MANDATORY_LOOP_FAILED`
- `AMBIGUOUS_PROGRAM`
- `OUTPUT_SCHEMA_CONFLICT`
- `EXECUTION_FAILED`
- `LOW_EVIDENCE`

Failures are data, not exceptions that silently select another path.

## 10. Testing

Test layers:

1. fiber and schema unit tests;
2. program-node execution tests;
3. grammar type-safety tests;
4. connection graph tests;
5. loop construction tests;
6. residual tests;
7. search and pruning tests;
8. refinement tests;
9. proposer contract tests with a fake provider;
10. Run 001 original regression;
11. Run 001 mutation regression;
12. anti-cheating scans;
13. deterministic replay;
14. frozen V1 and blind-protocol regression;
15. resource-limit and adversarial tests.

TDD is mandatory for each production capability.

## 11. CI

A dedicated workflow runs:

- frozen V1 source-byte checks;
- V1 tests;
- blind-protocol tests;
- V2 unit and integration tests;
- Run 001 regression;
- mutation regression;
- anti-cheating scans;
- deterministic replay;
- evidence manifest creation;
- artifact upload.

Model-assisted tests use a deterministic fake provider in CI. Live provider runs are separate evidence events.

## 12. Delivery sequence

1. commit this design;
2. commit a detailed TDD plan;
3. create implementation branch;
4. implement typed fibers and program graph;
5. implement grammar and connection graph;
6. implement loops and residuals;
7. implement deterministic search and refinement;
8. add Run 001 regression;
9. add proposer tier;
10. pass all gates;
11. freeze V2;
12. create and execute Run 002;
13. publish the full first-attempt result;
14. continue with new fresh suites until performance is both broad and repeatable.

## 13. Acceptance criteria

V2 engineering is complete only when:

- V1 and protocol bytes remain protected;
- all V2 tests pass;
- the Run 001 original gate passes;
- the mutation gate passes;
- accepted programs carry explicit closed-loop evidence;
- deterministic and model-assisted tiers are separable;
- the implementation branch is frozen before Run 002 generation;
- Run 002 produces a public first-attempt report regardless of score.

A “universal winner” label is not an implementation acceptance criterion. It is an empirical claim that requires repeated strong performance on fresh, externally retained task families.
