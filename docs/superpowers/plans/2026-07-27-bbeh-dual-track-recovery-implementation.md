# BBEH Dual-Track Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct BoardgameQA and Geometric Shapes, preserve honest general-compiler scores, produce separately labeled 100%-fit public-corpus lanes, and seal one GitHub-backed six-task 1,200-row structured closeout artifact.

**Architecture:** Each task has an isolated Track G implementation and a separate Track F residual layer. A shared evidence protocol generates target-blind predictions, seals canonical JSON bytes, verifies row identity, and scores only after seal verification. BoardgameQA uses a typed defeasible-logic compiler with background predicate evaluation; Geometric Shapes uses a planar segment graph and polygon classifier.

**Tech Stack:** Python 3.11, standard library only unless an existing repository dependency is already pinned, `pytest`, GitHub Actions, SHA-256 canonical JSON evidence.

## Global Constraints

- Benchmark pin: `80d12ca916b7158f22293fcf3144f4d3d854d4be`.
- Boardgame source pin: `tasksource/Boardgame-QA@78e38c3c8df3b4f6de7ae8bd1fc6a8bd1f31be56`.
- Track G must not select answers using row indices, prompt hashes, targets, or per-row output tables.
- Track F may use row-specific corrections only after the corresponding Track G first score is sealed.
- First-score files are immutable; target-informed revisions use new versioned paths.
- Exceptions and abstentions count wrong.
- All 200 rows per task must be present, ordered, input-hash verified, and byte-sealed.
- Fitted results must always be labeled `public-corpus-fit`, never unseen-test or generalization performance.
- Existing Zebra, Buggy Tables, Object Properties, and Time Arithmetic evidence must not be overwritten.

---

## File Map

- `research/universal_validation/bbeh_evidence_protocol.py`: shared canonicalization, generation, sealing, scoring, mismatch, and hash-manifest logic.
- `research/universal_validation/bbeh_boardgame_ir.py`: typed literals, rules, preferences, substitutions, and derivations.
- `research/universal_validation/bbeh_boardgame_source.py`: Boardgame-QA JSONL loading, theory parsing, and input-only grammar inventory.
- `research/universal_validation/bbeh_boardgame_parser.py`: native BBEH English-to-IR parser and reusable background predicate extraction.
- `research/universal_validation/bbeh_boardgame_inference.py`: defeasible proof search and preference resolution.
- `research/universal_validation/bbeh_boardgame_general_v1.py`: Track G audit, generation, and scoring entry point.
- `research/universal_validation/bbeh_boardgame_fit_v1.py`: Track F correction ledger and fitted prediction runner.
- `research/universal_validation/bbeh_geometric_general_v1.py`: SVG parser, segment normalization, cycle extraction, and shape classification.
- `research/universal_validation/bbeh_geometric_fit_v1.py`: fitted residual ledger for unresolved geometric rows.
- `research/universal_validation/bbeh_structured_six_task_closeout_v2.py`: six-task aggregation and evidence manifest.
- `.github/workflows/universal-structured-six-task-v2.yml`: pinned CI and artifact upload.
- Tests mirror every source file under `research/universal_validation/test_*.py`.

---

### Task 1: Shared Evidence Protocol

**Files:**
- Create: `research/universal_validation/bbeh_evidence_protocol.py`
- Create: `research/universal_validation/test_bbeh_evidence_protocol.py`

**Interfaces:**
- Produces: `canonical_json_bytes(payload) -> bytes`, `sha256_bytes(data) -> str`, `generate_predictions(examples, solver, task_name, output_dir, metadata) -> dict`, `score_predictions(examples, prediction_path, seal_path, score_path, equivalence=None) -> dict`, `write_sha256_manifest(output_dir) -> dict`.

- [ ] **Step 1: Write the failing canonicalization and seal tests**

```python
from pathlib import Path
import json
import pytest

from bbeh_evidence_protocol import canonical_json_bytes, generate_predictions, score_predictions


def test_canonical_json_is_stable_across_key_order():
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_score_rejects_modified_prediction_bytes(tmp_path: Path):
    examples = [{"input": "x", "target": "yes"}]
    generate_predictions(examples, lambda _: "yes", "demo", tmp_path, {})
    path = tmp_path / "predictions.json"
    payload = json.loads(path.read_text())
    payload["rows"][0]["prediction"] = "no"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="prediction seal mismatch"):
        score_predictions(examples, path, tmp_path / "predictions.sha256", tmp_path / "first_score.json")
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_evidence_protocol.py`

Expected: import failure for `bbeh_evidence_protocol`.

- [ ] **Step 3: Implement canonical generation and seal verification**

Use sorted, indented UTF-8 JSON with one trailing newline. Store only `index`, `input_sha256`, `prediction`, `error`, and `latency_seconds` during generation. Do not read `target` in `generate_predictions`.

- [ ] **Step 4: Add a target-access guard test**

```python
class GuardedExample(dict):
    def __getitem__(self, key):
        if key == "target":
            raise AssertionError("target accessed during generation")
        return super().__getitem__(key)


def test_generation_never_reads_target(tmp_path):
    examples = [GuardedExample(input="q", target="proved")]
    generate_predictions(examples, lambda _: "proved", "demo", tmp_path, {})
```

- [ ] **Step 5: Run GREEN and full local tests**

Run: `pytest -q research/universal_validation/test_bbeh_evidence_protocol.py`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add research/universal_validation/bbeh_evidence_protocol.py research/universal_validation/test_bbeh_evidence_protocol.py
git commit -m "feat: add sealed BBEH evidence protocol"
```

---

### Task 2: Boardgame Typed IR and Defeasible Inference Kernel

**Files:**
- Create: `research/universal_validation/bbeh_boardgame_ir.py`
- Create: `research/universal_validation/bbeh_boardgame_inference.py`
- Create: `research/universal_validation/test_bbeh_boardgame_inference.py`

**Interfaces:**
- Produces: `Literal(subject, predicate, object, negated=False)`, `Condition(literal, existential=False)`, `Rule(rule_id, antecedents, consequent)`, `Theory(facts, rules, preferences, query)`, `ProofResult(status, query_derivations, opposite_derivations)`, `prove(theory, background=None) -> ProofResult`.
- Status values: `proved`, `disproved`, `unknown`.

- [ ] **Step 1: Write RED tests for direct facts, conjunction, and explicit negation**

```python
def test_direct_positive_fact_is_proved():
    q = Literal("pigeon", "bring", "woodpecker")
    theory = Theory(facts=frozenset({q}), rules=(), preferences=frozenset(), query=q)
    assert prove(theory).status == "proved"


def test_opposite_fact_is_disproved():
    q = Literal("finch", "shout", "mermaid")
    theory = Theory(facts=frozenset({q.opposite()}), rules=(), preferences=frozenset(), query=q)
    assert prove(theory).status == "disproved"


def test_rule_requires_all_antecedents():
    a = Literal("pigeon", "take", "gadwall")
    b = Literal("pigeon", "shout", "peafowl", negated=True)
    q = Literal("pigeon", "bring", "woodpecker")
    rule = Rule("Rule2", (Condition(a), Condition(b)), q)
    assert prove(Theory(frozenset({a}), (rule,), frozenset(), q)).status == "unknown"
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_inference.py`

Expected: missing IR/inference imports.

- [ ] **Step 3: Implement immutable IR and forward fixed-point derivation**

Implement variable terms as strings beginning with `?`. Unify constants and variables positionally. Record supporting rule IDs on every derived literal. Stop only when no new undefeated literal is added.

- [ ] **Step 4: Add existential, preference, and cycle tests**

```python
def test_existential_antecedent_accepts_any_witness():
    fact = Literal("seal", "destroy", "frog")
    q = Literal("shark", "bring", "cougar", negated=True)
    rule = Rule("Rule5", (Condition(Literal("?x", "destroy", "frog"), existential=True),), q)
    assert prove(Theory(frozenset({fact}), (rule,), frozenset(), q)).status == "proved"


def test_preferred_rule_defeats_conflicting_rule_only_when_both_apply():
    trigger = Literal("duck", "hug", "pigeon")
    positive = Rule("Rule1", (Condition(trigger),), Literal("pigeon", "shout", "peafowl"))
    negative = Rule("Rule8", (Condition(trigger),), Literal("pigeon", "shout", "peafowl", True))
    theory = Theory(frozenset({trigger}), (positive, negative), frozenset({("Rule1", "Rule8")}), positive.consequent)
    assert prove(theory).status == "proved"


def test_unsupported_cycle_does_not_prove_itself():
    a = Literal("a", "p", None)
    b = Literal("b", "q", None)
    rules = (Rule("R1", (Condition(b),), a), Rule("R2", (Condition(a),), b))
    assert prove(Theory(frozenset(), rules, frozenset(), a)).status == "unknown"
```

- [ ] **Step 5: Implement transitive preference closure and contradiction resolution**

A derivation is defeated only by an applicable opposing derivation whose rule is strictly stronger through the transitive preference graph. Two undefeated opposing derivations yield `unknown`.

- [ ] **Step 6: Run GREEN and commit**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_inference.py`

```bash
git add research/universal_validation/bbeh_boardgame_ir.py research/universal_validation/bbeh_boardgame_inference.py research/universal_validation/test_bbeh_boardgame_inference.py
git commit -m "feat: add BoardgameQA defeasible inference kernel"
```

---

### Task 3: Boardgame Structured Source Parser and Grammar Inventory

**Files:**
- Create: `research/universal_validation/bbeh_boardgame_source.py`
- Create: `research/universal_validation/test_bbeh_boardgame_source.py`

**Interfaces:**
- Consumes: `Literal`, `Condition`, `Rule`, `Theory`.
- Produces: `load_source_rows(path) -> Iterator[dict]`, `parse_theory(text, goal) -> Theory`, `audit_source_grammar(path) -> dict`.

- [ ] **Step 1: Write a failing parser test from the pinned source syntax**

```python
SOURCE = """Facts:
\t(coyote, swear, pigeon)
\t~(shark, capture, gorilla)
Rules:
\tRule2: ~(X, shout, peafowl)^(X, take, gadwall) => (X, bring, woodpecker)
\tRule5: exists X (X, destroy, frog) => ~(shark, bring, cougar)
Preferences:
\tRule1 > Rule8
"""


def test_parse_structured_theory():
    theory = parse_theory(SOURCE, "(pigeon, bring, woodpecker)")
    assert Literal("coyote", "swear", "pigeon") in theory.facts
    assert Literal("shark", "capture", "gorilla", True) in theory.facts
    assert theory.rules[0].antecedents[0].literal.negated
    assert theory.rules[1].antecedents[0].existential
    assert ("Rule1", "Rule8") in theory.preferences
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_source.py`

- [ ] **Step 3: Implement strict line parser**

Parse tuple payloads without `eval`. Normalize source variable `X` to `?x`. Preserve opaque object descriptors such as `a card whose color is one of the rainbow colors` as strings for the background evaluator.

- [ ] **Step 4: Add full 37,500-row input-only inventory**

The audit must count rows, facts, rules, preferences, existential conditions, negations, unique predicate arities, and parse failures. It must never access `label` or `proof`.

- [ ] **Step 5: Run the source audit**

Run:

```bash
python -m research.universal_validation.bbeh_boardgame_source \
  --source .external/boardgame_qa/boardgame_qa_all.jsonl.gz \
  --out artifacts/boardgame_source_audit.json
```

Expected: `rows == 37500`, `parse_failures == 0` before proceeding.

- [ ] **Step 6: Commit**

```bash
git add research/universal_validation/bbeh_boardgame_source.py research/universal_validation/test_bbeh_boardgame_source.py
git commit -m "feat: parse pinned BoardgameQA structured theories"
```

---

### Task 4: Native Boardgame Prompt Parser and Background Predicates

**Files:**
- Create: `research/universal_validation/bbeh_boardgame_parser.py`
- Create: `research/universal_validation/test_bbeh_boardgame_parser.py`

**Interfaces:**
- Produces: `parse_prompt(prompt) -> Theory`, `evaluate_background(required: Literal, facts: frozenset[Literal]) -> bool`, `audit_prompt_grammar(examples) -> dict`.

- [ ] **Step 1: Write RED tests for the known fragile grammar families**

```python
def test_parenthetical_subject_is_not_lost():
    rule = parse_rule("Rule1: The stork will not pay money to the beaver if it (the stork) is watching a movie that was released after world war 2 started.")
    assert rule.consequent == Literal("stork", "pay", "beaver", True)


def test_relative_clause_consequent_binds_rule_variable():
    rule = parse_rule("The living creature that hides the cards that she has from the bulldog will never want to see the dugong.")
    assert rule.consequent.subject == "?x"
    assert rule.antecedents[0].literal.subject == "?x"


def test_generic_weapon_phrase_is_relational():
    fact = parse_fact("The dalmatian borrows one of the weapons of the fish.")
    assert fact == Literal("dalmatian", "borrow", "fish")
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_parser.py`

- [ ] **Step 3: Implement prompt section extraction**

Split facts, numbered rules, preference sentences, and final query using anchored markers. Parse the final answer vocabulary from the prompt but always return canonical `proved`, `disproved`, or `unknown`.

- [ ] **Step 4: Implement reusable sentence templates**

Implement positive/negative facts, unary attributes, binary relations, conjunction, `if`, `whenever`, `in the case where`, existential phrases, pronouns, possessives, and quoted consequents. Reject unmatched text with an explicit parse error containing the source sentence.

- [ ] **Step 5: Add background predicate tests**

```python
def test_rainbow_color_background_entails_descriptor():
    facts = frozenset({Literal("wolf", "has", "a card that is indigo in color")})
    required = Literal("wolf", "has", "a card whose color is one of the rainbow colors")
    assert evaluate_background(required, facts)


def test_name_initial_comparison():
    facts = frozenset({Literal("crab", "named", "Tessa"), Literal("cougar", "named", "Tarzan")})
    required = Literal("crab", "name_initial_matches", "cougar")
    assert evaluate_background(required, facts)
```

Cover numeric money comparison, age-to-month conversion, year thresholds, color prefixes, country-flag colors, shape dimensions, friend counts, locations, professions, containers, and object aliases.

- [ ] **Step 6: Audit all 200 BBEH BoardgameQA prompts without targets**

Run:

```bash
python -m research.universal_validation.bbeh_boardgame_parser \
  --task .external/bbeh/bbeh/benchmark_tasks/bbeh_boardgame_qa/task.json \
  --audit-only \
  --out artifacts/boardgame_general_v1/grammar_audit.json
```

Expected before scoring: 200 parsed prompts, zero unparsed facts, rules, preferences, and queries.

- [ ] **Step 7: Commit**

```bash
git add research/universal_validation/bbeh_boardgame_parser.py research/universal_validation/test_bbeh_boardgame_parser.py
git commit -m "feat: compile BoardgameQA prompts into typed theories"
```

---

### Task 5: Boardgame Track G Runner and Immutable First Score

**Files:**
- Create: `research/universal_validation/bbeh_boardgame_general_v1.py`
- Create: `research/universal_validation/test_bbeh_boardgame_general_v1.py`

**Interfaces:**
- Produces: `solve(prompt) -> str`, CLI output under `artifacts/boardgame_general_v1/`.

- [ ] **Step 1: Write RED end-to-end tests**

Use one proved, one disproved, and one unknown synthetic prompt. Assert `solve()` returns the canonical label and never imports the fitted module.

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_general_v1.py`

- [ ] **Step 3: Implement `solve()` as parse then prove**

```python
def solve(prompt: str) -> str:
    theory = parse_prompt(prompt)
    return prove(theory, background=evaluate_background).status
```

- [ ] **Step 4: Generate target-blind predictions and seal them**

Run:

```bash
python -m research.universal_validation.bbeh_boardgame_general_v1 \
  --task .external/bbeh/bbeh/benchmark_tasks/bbeh_boardgame_qa/task.json \
  --out artifacts/boardgame_general_v1 \
  --phase generate
```

Expected: 200 rows, zero exceptions, 100% coverage, prediction seal written.

- [ ] **Step 5: Score once and preserve the result**

Run:

```bash
python -m research.universal_validation.bbeh_boardgame_general_v1 \
  --task .external/bbeh/bbeh/benchmark_tasks/bbeh_boardgame_qa/task.json \
  --out artifacts/boardgame_general_v1 \
  --phase score
```

Do not edit `first_score.json` after this command. Copy mismatches to `mismatches.json` and classify them by parser, background, inference, or annotation family.

- [ ] **Step 6: For each general repair, add a minimal failing test before code**

Version target-informed repairs as `bbeh_boardgame_general_v2.py`; keep v1 source and artifacts unchanged.

- [ ] **Step 7: Commit source and immutable first-score metadata**

```bash
git add research/universal_validation/bbeh_boardgame_general_v1.py research/universal_validation/test_bbeh_boardgame_general_v1.py
git commit -m "feat: seal BoardgameQA general compiler v1"
```

---

### Task 6: Boardgame Track F Public-Corpus Fit

**Files:**
- Create: `research/universal_validation/bbeh_boardgame_fit_v1.py`
- Create: `research/universal_validation/test_bbeh_boardgame_fit_v1.py`
- Create after general scoring: `research/universal_validation/data/boardgame_fit_v1_corrections.json`

**Interfaces:**
- Consumes immutable Track G predictions.
- Produces fitted predictions, correction ledger, and `public-corpus-fit` result.

- [ ] **Step 1: Write separation tests**

```python
def test_fit_layer_does_not_mutate_general_predictions(tmp_path):
    before = general_path.read_bytes()
    run_fit(general_path, task_path, corrections_path, tmp_path)
    assert general_path.read_bytes() == before


def test_every_changed_prediction_has_a_ledger_entry():
    result = run_fit(...)
    assert result["changed_rows"] == len(result["corrections"])
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_boardgame_fit_v1.py`

- [ ] **Step 3: Implement strict correction schema**

Each entry must contain `index`, `input_sha256`, `general_prediction`, `fitted_prediction`, `mechanism`, and `reason`. Reject stale hashes or a general prediction mismatch.

- [ ] **Step 4: Build corrections from the sealed mismatch ledger**

Use the smallest correction set needed. Direct target lookup is allowed only here and must remain explicit in the JSON ledger.

- [ ] **Step 5: Generate, seal, and score Track F**

Acceptance: 200/200 strict, 100% coverage, Track G prediction SHA unchanged.

- [ ] **Step 6: Commit**

```bash
git add research/universal_validation/bbeh_boardgame_fit_v1.py research/universal_validation/test_bbeh_boardgame_fit_v1.py research/universal_validation/data/boardgame_fit_v1_corrections.json
git commit -m "feat: add labeled BoardgameQA public-corpus fit lane"
```

---

### Task 7: Geometric Shapes Track G Compiler

**Files:**
- Create: `research/universal_validation/bbeh_geometric_general_v1.py`
- Create: `research/universal_validation/test_bbeh_geometric_general_v1.py`

**Interfaces:**
- Produces: `parse_svg_segments(prompt) -> list[Segment]`, `normalize_segments(segments, tolerance=1e-4) -> list[Segment]`, `extract_simple_cycles(segments) -> list[Polygon]`, `classify_polygon(polygon) -> set[int]`, `solve(prompt) -> str`.

- [ ] **Step 1: Write RED tests for segment parsing and collinear merging**

```python
def test_parse_multiple_moveto_lineto_groups():
    segments = parse_svg_segments("Suppose we draw this SVG path element: M 0,0 L 2,0 M 2,0 L 2,2 . Out of")
    assert len(segments) == 2


def test_collinear_split_edges_merge_for_shape_counting():
    segs = [S((0,0),(1,0)), S((1,0),(2,0)), S((2,0),(2,1)), S((2,1),(0,1)), S((0,1),(0,0))]
    assert len(normalize_segments(segs)) == 4
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_geometric_general_v1.py`

- [ ] **Step 3: Implement numeric-tolerant planar graph construction**

Snap endpoints within `1e-4`, split at intersections, remove duplicate undirected segments, merge degree-2 collinear chains, and preserve adjacency.

- [ ] **Step 4: Add polygon classification tests**

Cover rectangle, square, non-right triangle, right triangle, non-rectangular parallelogram, exactly-one-pair trapezoid, irregular convex pentagon, irregular concave pentagon, regular pentagon, and regular hexagon. Assert that internal diagonals disqualify the “no diagonals drawn” categories.

- [ ] **Step 5: Implement option parsing and exact answer formatting**

Parse each option’s shape-number set and return the unique matching letter in parentheses, for example `(E)`.

- [ ] **Step 6: Run an input-only 200-row geometry audit**

Expected: every SVG parses, every option list parses, no exceptions.

- [ ] **Step 7: Generate, seal, and first-score Track G**

Write artifacts under `artifacts/geometric_general_v1/`. Preserve the first score before any target-informed repair.

- [ ] **Step 8: Commit**

```bash
git add research/universal_validation/bbeh_geometric_general_v1.py research/universal_validation/test_bbeh_geometric_general_v1.py
git commit -m "feat: reconstruct geometric shapes compiler v1"
```

---

### Task 8: Geometric Shapes Track F Public-Corpus Fit

**Files:**
- Create: `research/universal_validation/bbeh_geometric_fit_v1.py`
- Create: `research/universal_validation/test_bbeh_geometric_fit_v1.py`
- Create after general scoring: `research/universal_validation/data/geometric_fit_v1_corrections.json`

**Interfaces:** Same strict correction schema as BoardgameQA.

- [ ] **Step 1: Reuse the fit-separation contract through tests**

Assert immutable general SHA, exact row-hash matching, and one ledger entry per changed row.

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_geometric_fit_v1.py`

- [ ] **Step 3: Implement fitted residual application**

Import only the shared evidence protocol, never modify or monkey-patch the general solver.

- [ ] **Step 4: Create corrections for sealed general mismatches**

Label mechanisms as `row-signature`, `option-map`, or `direct-public-label`.

- [ ] **Step 5: Generate, seal, and score**

Acceptance: 200/200 strict, 100% coverage, unchanged general prediction SHA.

- [ ] **Step 6: Commit**

```bash
git add research/universal_validation/bbeh_geometric_fit_v1.py research/universal_validation/test_bbeh_geometric_fit_v1.py research/universal_validation/data/geometric_fit_v1_corrections.json
git commit -m "feat: add labeled geometry public-corpus fit lane"
```

---

### Task 9: Six-Task Structured Closeout Aggregator

**Files:**
- Create: `research/universal_validation/bbeh_structured_six_task_closeout_v2.py`
- Create: `research/universal_validation/test_bbeh_structured_six_task_closeout_v2.py`

**Interfaces:**
- Produces `aggregate(task_results: dict[str, dict]) -> dict` with per-task scores, 1,200-row totals, micro, arithmetic macro, and harmonic mean.

- [ ] **Step 1: Write RED metric tests**

```python
def test_aggregate_counts_all_1200_rows():
    results = {name: {"n": 200, "correct": 200} for name in SIX_TASKS}
    out = aggregate(results)
    assert out["n"] == 1200
    assert out["correct"] == 1200
    assert out["micro"] == 1.0
    assert out["harmonic"] == 1.0
```

- [ ] **Step 2: Run RED**

Run: `pytest -q research/universal_validation/test_bbeh_structured_six_task_closeout_v2.py`

- [ ] **Step 3: Implement immutable artifact ingestion**

Load Zebra, Buggy Tables, Object Properties, Time Arithmetic, BoardgameQA, and Geometric Shapes score files. Verify expected task names, 200 rows each, prediction seals, task hashes, and source hashes.

- [ ] **Step 4: Report Track G and Track F separately**

Track G uses general Boardgame and geometry results plus existing general exact compilers. Track F uses fitted Boardgame and geometry, and may use a separately labeled typed-time route in addition to strict exact-string time.

- [ ] **Step 5: Create one combined hash manifest**

Include every source file, task file, prediction file, score file, correction ledger, and audit file.

- [ ] **Step 6: Run acceptance gate**

Required fitted strict result: 1,200/1,200. Required general result: reported exactly as observed, without substitution from Track F.

- [ ] **Step 7: Commit**

```bash
git add research/universal_validation/bbeh_structured_six_task_closeout_v2.py research/universal_validation/test_bbeh_structured_six_task_closeout_v2.py
git commit -m "feat: seal dual-track six-task structured closeout"
```

---

### Task 10: GitHub Actions Reproduction Workflow

**Files:**
- Create: `.github/workflows/universal-structured-six-task-v2.yml`

**Interfaces:** Uploads artifact `universal-structured-six-task-v2`.

- [ ] **Step 1: Add a workflow syntax validation test command**

Run locally: `python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/universal-structured-six-task-v2.yml').read_text())"` when PyYAML is available; otherwise use `ruby -e "require 'yaml'; YAML.load_file(ARGV[0])" .github/workflows/universal-structured-six-task-v2.yml`.

- [ ] **Step 2: Implement exact-head checkout and pinned data acquisition**

Checkout `${{ github.event.pull_request.head.sha || github.sha }}`. Clone BBEH and checkout the pinned commit. Download or reconstruct Boardgame-QA at the pinned revision and verify the known export digest `76736628f0572a4de54262440af7a66499236d89d70c8a591ce9d35c78b0168c`.

- [ ] **Step 3: Run tests before corpus generation**

```yaml
- run: pytest -q research/universal_validation/test_bbeh_evidence_protocol.py research/universal_validation/test_bbeh_boardgame_*.py research/universal_validation/test_bbeh_geometric_*.py research/universal_validation/test_bbeh_structured_six_task_closeout_v2.py
```

- [ ] **Step 4: Run audits, Track G, Track F, and aggregation in order**

The workflow must stop before Track F if either general first-score artifact is missing or its seal fails.

- [ ] **Step 5: Recompute all hashes independently**

Use `sha256sum -c artifacts/structured_six_task_closeout_v2/SHA256SUMS` and fail on any mismatch.

- [ ] **Step 6: Upload the combined artifact with 30-day retention**

- [ ] **Step 7: Commit and push**

```bash
git add .github/workflows/universal-structured-six-task-v2.yml
git commit -m "ci: reproduce dual-track structured closeout"
git push origin universal-structured-residual-v1
```

---

### Task 11: Independent Verification and Checkpoint Update

**Files:**
- Create: `research/universal_validation/checkpoints/2026-07-27/STRUCTURED_RECOVERY_RESULTS.md`
- Modify: `research/universal_validation/checkpoints/2026-07-27/SCOREBOARD.json`
- Modify: `research/universal_validation/checkpoints/2026-07-27/STATE.md`

**Interfaces:** Human-readable and machine-readable record of exact artifact IDs, digests, commits, and claims boundary.

- [ ] **Step 1: Download the successful Actions artifact independently**

Recompute the ZIP SHA-256 and every internal manifest entry outside the workflow.

- [ ] **Step 2: Verify result invariants**

Confirm 1,200 unique row identities, six task hashes, no missing rows, no duplicate rows, valid prediction seals, and Track G source/prediction hashes unchanged after Track F.

- [ ] **Step 3: Update the scoreboard with evidence classes**

Record `github_backed_general`, `github_backed_public_corpus_fit`, and `historical_superseded` separately. Do not delete historical values.

- [ ] **Step 4: Run full repository validation**

Run the focused test suite plus existing Zebra closeout tests. Inspect the GitHub Actions job log for warnings, skipped tests, or hidden retries.

- [ ] **Step 5: Commit checkpoint**

```bash
git add research/universal_validation/checkpoints/2026-07-27/STRUCTURED_RECOVERY_RESULTS.md research/universal_validation/checkpoints/2026-07-27/SCOREBOARD.json research/universal_validation/checkpoints/2026-07-27/STATE.md
git commit -m "docs: checkpoint recovered structured BBEH routes"
git push origin universal-structured-residual-v1
```

---

## Self-Review Results

- Spec coverage: Boardgame Track G/F, geometry Track G/F, shared evidence, six-task aggregation, CI, and checkpoint verification are all assigned to concrete tasks.
- Placeholder scan: no `TBD`, `TODO`, “implement later,” or undefined acceptance steps remain.
- Type consistency: Track G solvers return canonical strings; all task runners consume the same evidence protocol; both Track F lanes use the same correction schema; the aggregator consumes score dictionaries with `n` and `correct`.
- Scope boundary: semantic residual improvement and full 4,520-row fitting are deliberately excluded until the six-task structured artifact passes.

## Completion Gate

The plan is complete only when GitHub Actions produces one independently verified artifact with:

- BoardgameQA Track G first score preserved;
- BoardgameQA Track F at 200/200;
- Geometric Shapes Track G first score preserved;
- Geometric Shapes Track F at 200/200;
- fitted six-task strict total at 1,200/1,200;
- Track G six-task result reported separately;
- complete SHA-256 verification and no Track F influence on Track G outputs.
