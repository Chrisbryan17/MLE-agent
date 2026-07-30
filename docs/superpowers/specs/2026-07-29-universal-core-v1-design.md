# Universal Core V1 Design

**Status:** Approved design baseline  
**Date:** 2026-07-29  
**Development branch:** `universal-core-v1-design`  
**Immutable archive branch:** `archive/universal-bbeh-dual-track-4520-2026-07-28`  
**Immutable archive commit:** `a0c099a41c85f267ca6323235a019b2052107873`

## 1. Purpose

Universal Core V1 is a benchmark-agnostic reasoning compiler for private evaluation suites. It receives one unknown task schema, natural-language instructions, 3–20 labeled demonstrations, and hidden unlabeled rows. It must infer the task, synthesize a reusable solver, verify that solver, freeze it, and execute it unchanged on every hidden row.

The system is designed to replace benchmark-name routing and row-specific corrections with task induction, typed representations, program synthesis, deterministic execution, and sealed evaluation.

V1 is the strongest practical first implementation, not the architectural ceiling. Every interface must permit later expansion toward instruction-only induction, mixed task schemas, learned operators, multimodal reasoning, open-world retrieval, and previously unseen task-family generalization.

## 2. Scientific claim boundary

A valid Universal Core result requires all of the following:

- The benchmark name and task identifier do not influence solver selection.
- Hidden targets are unavailable before prediction sealing.
- No input-hash answer mappings, row-specific exceptions, or target-informed correction ledgers are used.
- The synthesized solver is frozen before hidden execution.
- The first prediction artifact is immutable and independently verifiable.
- Evaluation reports raw accuracy, coverage, abstention rate, and failure classifications.

V1 may claim performance only under the protocol actually executed. It must not represent public-corpus adaptation as private-benchmark generalization.

## 3. Archive and non-destruction policy

The verified 4,520-row dual-track system remains preserved at the archive branch and commit listed above. Universal Core development is additive and occurs on a separate branch derived from that exact commit.

The following rules are mandatory:

1. Do not delete, rewrite, squash, force-update, or silently relocate archived source, workflows, checkpoints, manifests, predictions, or evidence.
2. Do not modify the archive branch.
3. Any later namespace migration must copy first, verify byte identity, add restoration tests, and occur in a separate reviewed change.
4. Public-corpus fitting machinery must remain explicitly labeled and isolated from Universal Core execution.
5. Universal Core tests must fail if archived behavior or restoration evidence becomes unavailable.

## 4. V1 scope

### 4.1 Supported evaluation contract

Each evaluation batch contains exactly one unknown task schema and provides:

- natural-language task instructions;
- 3–20 labeled demonstrations, optimized for useful induction around five examples;
- one or more hidden unlabeled inputs;
- an optional explicit output schema;
- inert metadata retained for audit purposes only.

The system must support variable demonstration counts without changing its architecture or evaluation protocol.

### 4.2 Initial task coverage

V1 officially targets:

- propositional and relational logic;
- finite constraint satisfaction;
- arithmetic and bounded algebra;
- temporal reasoning;
- spatial and geometric relations;
- graphs, paths, reachability, and ordering;
- counting, sorting, ranking, matching, grouping, and aggregation;
- rule-based classification;
- lightweight semantic entailment, intent, relation, local causality, contextual ambiguity, taxonomy, and attribute classification.

V1 does not claim complete support for unconstrained open-world factual recall, deep cultural interpretation, unrestricted recommendations, sarcasm, or arbitrary long-horizon semantic reasoning. The architecture must permit those capabilities later.

## 5. Canonical input and output contracts

### 5.1 Task package

The schema normalizer produces a canonical `TaskPackage` with these logical fields:

- `instructions`: normalized instruction text;
- `demonstrations`: ordered labeled input-output pairs;
- `hidden_inputs`: ordered unlabeled inputs;
- `output_schema`: explicit or inferred answer type and formatting rules;
- `metadata`: inert provenance and evaluator metadata;
- `package_digest`: content digest over the normalized evaluation inputs.

Task names, filenames, benchmark labels, row indices, and metadata values must not be available to routing or synthesis policy unless explicitly part of the task instructions themselves.

### 5.2 Result package

The system emits:

- ordered predictions;
- per-row status and confidence;
- abstentions and typed failure reasons;
- inferred task specification;
- accepted solver representation or source;
- verification evidence;
- runtime configuration and dependency versions;
- resource-usage records;
- solver digest;
- prediction digest;
- immutable first-attempt manifest.

## 6. Architecture

The primary data flow is:

```text
Task package
    -> schema normalization
    -> task-specification induction
    -> typed universal IR
    -> candidate solver synthesis
    -> verification and counterexample search
    -> solver selection
    -> freeze and cryptographic seal
    -> sandboxed hidden execution
    -> sealed prediction and audit package
```

Each stage has a narrow interface and may be tested independently.

## 7. Components

### 7.1 Schema normalizer

The normalizer converts external benchmark formats into the canonical task package. It validates required fields, preserves row order, canonicalizes encodings, computes digests, and rejects malformed or ambiguous packaging.

The normalizer must not infer task semantics or choose a solver.

### 7.2 Task-specification induction

The induction engine infers a machine-readable task specification containing:

- input field types and structural regularities;
- entities, attributes, relations, variables, and domains;
- relevant and likely incidental information;
- transformations, predicates, constraints, objectives, and invariants;
- required answer type and formatting;
- ambiguity, confidence, and competing hypotheses;
- candidate reasoning capabilities required by the task.

The output is a typed specification, not only a prose explanation. Competing specifications remain explicit until verification separates them.

### 7.3 Universal typed intermediate representation

The IR supports:

- booleans, numbers, strings, symbols, enums, lists, sets, multisets, maps, records, tables, graphs, trees, intervals, coordinates, and distributions;
- typed entities, attributes, relations, predicates, quantifiers, implications, exclusions, equations, inequalities, temporal relations, spatial relations, objectives, and answer schemas;
- provenance links from parsed facts and inferred rules back to demonstrations and instructions;
- deterministic serialization for hashing, replay, and audit;
- extension points for later learned or domain-specific operators without changing the execution contract.

Existing exact solvers are exposed as reusable operators or templates behind typed interfaces. They are not selected by benchmark names.

### 7.4 Trusted operator library

The preferred synthesis target is an operator graph composed from allowlisted, deterministic primitives, including:

- parse, extract, normalize, map, filter, group, join, project, sort, count, aggregate, compare, rank, select, and format;
- unify, deduce, propagate, search, backtrack, solve constraints, evaluate rules, and prove or refute;
- traverse graphs, compute paths, detect cycles, match structures, and optimize bounded objectives;
- evaluate expressions, transform coordinates, simulate finite state, classify, and calibrate confidence.

Every operator defines input types, output types, determinism guarantees, resource bounds, failure modes, and test obligations.

### 7.5 Hybrid solver synthesis

Candidate construction follows this strict preference order:

1. Compose trusted typed operators.
2. Instantiate and parameterize reusable algorithmic templates.
3. Generate restricted code only when the first two forms cannot express a supported task.

Candidate ranking considers demonstration agreement, verification coverage, description length, operator trust level, runtime cost, stability under perturbation, and uncertainty.

A candidate that reproduces demonstrations through memorization but fails invariance or generated-instance checks must be rejected.

### 7.6 Restricted-code fallback

Generated code is untrusted and executes through a capability-limited sandbox with:

- no network access;
- no subprocess or shell access;
- no arbitrary host filesystem access;
- no package installation;
- no reflection over host internals;
- an allowlist of modules and built-ins;
- deterministic seeds and locale;
- strict CPU, memory, recursion, output-size, and wall-time budgets;
- serialized task inputs and outputs only;
- complete source capture and hashing before execution.

The sandbox must fail closed. A sandbox-policy violation invalidates the candidate rather than relaxing policy.

### 7.7 Verification and counterexample engine

A candidate solver is accepted only after layered verification:

1. Exact agreement with all demonstrations.
2. Leave-one-demonstration-out induction and replay where the demonstration budget permits it.
3. Type, schema, determinism, and output-format validation.
4. Metamorphic tests derived from inferred invariants.
5. Synthetic edge cases and fresh generated instances where a valid generator can be inferred or constructed.
6. Mutation testing against plausible incorrect solvers.
7. Contradiction, ambiguity, and underdetermination checks.
8. Differential comparison among independently constructed candidates.
9. Adversarial counterexample search within bounded domains.
10. Minimum-complexity preference among equivalently verified candidates.

Verification evidence must record which checks ran, which could not run, and why. Missing evidence lowers confidence; it is never silently treated as a pass.

### 7.8 Solver selection and abstention

The selector accepts a solver only when verification meets a configurable threshold appropriate to the task and evidence budget. Otherwise the batch or affected rows receive a typed failure status.

Required statuses are:

- `SOLVED`;
- `AMBIGUOUS_TASK`;
- `INSUFFICIENT_DEMONSTRATIONS`;
- `UNSUPPORTED_OPERATION`;
- `VERIFICATION_FAILED`;
- `EXECUTION_FAILED`;
- `OUTPUT_SCHEMA_CONFLICT`;
- `LOW_CONFIDENCE`.

Abstention is visible in scoring and cannot be used to hide weakness.

### 7.9 Freeze and seal protocol

Before processing hidden rows, the system freezes and hashes:

- normalized instructions and demonstrations;
- inferred specification;
- solver operator graph or restricted source;
- runtime configuration;
- dependency versions;
- verification evidence;
- random seeds;
- resource limits;
- solver digest and timestamp.

After sealing, no solver, prompt, parameter, dependency, or policy change is permitted for that evaluation attempt. Any revision creates a separately versioned attempt and preserves the original first score.

### 7.10 Hidden execution

The frozen solver processes every hidden row under identical policy and resource limits. Hidden rows may differ in length and values, but may not trigger manual routing or solver edits.

Execution records per-row status, prediction, confidence, runtime, and deterministic error details. Targets are introduced only after the ordered prediction artifact is sealed.

## 8. Anti-cheating and benchmark-agnostic controls

Automated tests must demonstrate invariance to:

- randomized task names and filenames;
- changed row ordering;
- demonstration reordering where task semantics are order-invariant;
- irrelevant metadata changes;
- entity and value renaming;
- equivalent instruction paraphrases;
- unseen row hashes;
- non-semantic whitespace and serialization changes.

The implementation must scan Universal Core execution paths for prohibited dependencies on task identifiers, public-target ledgers, row hashes, or fitted-answer artifacts.

## 9. Error handling

Errors are typed, deterministic, and included in the audit package. The system must never silently:

- substitute a benchmark-specific solver;
- access a target-informed correction path;
- relax sandbox constraints;
- alter a frozen solver;
- coerce incompatible output schemas;
- drop failed hidden rows;
- replace an immutable first prediction artifact.

Recoverable parsing issues may be normalized only before package sealing and must be recorded.

## 10. Testing strategy

### 10.1 Unit tests

Cover task-package normalization, typed IR construction, operator contracts, serialization, hashing, sandbox boundaries, statuses, sealing, and deterministic replay.

### 10.2 Induction tests

Hide task names and require successful specification and solver induction from instructions plus demonstrations alone.

### 10.3 Fresh-instance tests

For supported task families, generate instances not available during solver construction. Separate generators from solvers and verify that changing seeds and values does not change routing behavior.

### 10.4 Unseen-family holdouts

Reserve complete task families from development. Freeze the system, evaluate once, seal predictions, and reveal targets only afterward.

### 10.5 Adversarial and security tests

Test malicious instructions, code-injection attempts, resource exhaustion, nondeterminism, filesystem escape, network access, subprocess creation, oversized outputs, serialization attacks, and prompt content designed to bypass freeze or audit policy.

### 10.6 Archive regression tests

Verify that the archived commit, branch, artifact identity, restoration route, and evidence remain available and unchanged throughout V1 development.

## 11. Evaluation metrics

Every evaluation reports:

- raw exact-match or task-defined accuracy;
- coverage;
- accuracy among attempted rows;
- coverage-adjusted accuracy;
- abstention rate;
- solver-induction success rate;
- verification-pass rate;
- deterministic replay rate;
- task-family and operation-family breakdowns;
- time, memory, and synthesis cost;
- first-attempt score separately from all later revisions.

Private, unseen task-family performance is the primary progress metric. Public benchmark scores remain diagnostic and explicitly labeled.

## 12. V1 acceptance criteria

Universal Core V1 is complete only when it can:

1. Ingest one unknown task schema with 3–20 demonstrations.
2. Ignore randomized benchmark and task identifiers.
3. Infer and serialize a typed task specification.
4. Synthesize at least one solver through the trusted operator path.
5. Use the restricted-code fallback safely for at least one supported task requiring it.
6. Verify candidates with demonstration replay plus at least two nontrivial verification modes.
7. Freeze and hash the accepted solver before hidden execution.
8. Execute hidden rows without target access or manual intervention.
9. Produce immutable predictions and a complete audit package.
10. Reproduce outputs deterministically from the sealed package.
11. Pass anti-cheating, sandbox, unseen-hash, and archive-regression tests.
12. Preserve first-attempt scores and distinguish them from revisions.

Accuracy targets are established in the implementation plan after baseline harnesses exist. No acceptance threshold may be retroactively chosen to disguise poor generalization.

## 13. Peak-form roadmap

The architecture must support later additions without replacing its evaluation contract:

- instruction-only and zero-shot task induction;
- multiple unknown task schemas in one batch;
- automatic clustering and solver allocation;
- learned operator discovery and safe IR extension;
- neural-symbolic semantic grounding;
- open-world retrieval with provenance and frozen evidence snapshots;
- multimodal inputs and outputs;
- active demonstration selection;
- recursive solver improvement before freeze;
- calibrated uncertainty and selective prediction;
- cross-task transfer and persistent reusable abstractions;
- independent evaluation on entirely unseen private task families.

The long-term objective is maximum reliable performance on privately held, previously unseen task families under a sealed first-attempt protocol—not merely closure of known public corpora.
