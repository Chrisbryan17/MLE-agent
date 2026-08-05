# Dihedral Quadrant Mosaic Design

## Objective

Extend ARC grid induction with a generic primitive for outputs formed as a 2-by-2 mosaic of dihedral transforms of the source grid. Development remains restricted to the 1,000 ARC training tasks. The frozen V2.1 core remains byte-identical, and the public ARC evaluation set is not rerun.

## Evidence and expected gain

An exhaustive training-only scan found nine currently grammar-exhausted tasks whose demonstrations and hidden targets are exactly represented by this family:

- `0c786b71`
- `3af2c5a8`
- `46442a0e`
- `62c24649`
- `67e8384a`
- `7953d61e`
- `7fe24cdd`
- `833dafe3`
- `ed98d772`

For all nine tasks, the fitting programs produce one hidden-output equivalence class and the class matches the training target. The scan found no wrong completed hidden output and no ambiguity for this family.

Expected cumulative corpus result after integration:

- 78 correct and accepted rows out of 1,076
- zero incorrect accepted rows
- zero runner failures
- one preserved `AMBIGUOUS_PROGRAM` task (`60b61512`)
- 997 `GRAMMAR_EXHAUSTED` rows

## Program model

The new program kind is `dihedral_quadrant_mosaic` with four ordered transform fields:

```json
{
  "kind": "dihedral_quadrant_mosaic",
  "top_left": "identity",
  "top_right": "reflect_columns",
  "bottom_left": "reflect_rows",
  "bottom_right": "rotate_180"
}
```

Each field is one of the eight square-grid dihedral actions:

- `identity`
- `rotate_90`
- `rotate_180`
- `rotate_270`
- `reflect_columns`
- `reflect_rows`
- `reflect_main_diagonal`
- `reflect_anti_diagonal`

For rectangular grids, only transforms that preserve the source shape may occupy a quadrant. Quarter-turn and diagonal transforms are therefore excluded unless source height equals source width.

## Candidate derivation

The generator activates only when every demonstration output has dimensions exactly twice the source height and twice the source width.

For each of the four output quadrants independently:

1. split every demonstration output into source-sized quadrants;
2. evaluate every shape-preserving dihedral transform of the corresponding source;
3. retain transform names that reproduce that quadrant in every demonstration.

If any quadrant has no supported transform, the generator emits no programs and records `NO_SUPPORTED_QUADRANT_TRANSFORM`.

Otherwise, it emits the deterministic Cartesian product of the four retained transform sets. Transform order is fixed by the list above, making program order and trace output deterministic.

No transform is preferred merely because it is simpler or appears first. Symmetric demonstrations may support multiple named transforms. Those hypotheses remain explicit so an asymmetric hidden input can distinguish them. Existing output-equivalence consensus accepts only when all surviving hidden predictions agree and abstains when they diverge.

## Execution

Execution applies the four named transforms to the source grid, verifies that every transformed grid has the source shape, and concatenates them into two quadrant rows. It rejects outputs exceeding ARC's 30-by-30 bounds.

The implementation lives in a focused module:

- `research/universal_core/holonomy_v2_2/quadrant_mosaic.py`

The shared interpreter adds one dispatch case, and the mechanistic runtime adds one generator batch. The grid grammar version advances from `grid-v2.2-9` to `grid-v2.2-10`.

## Observability

The existing mechanistic runtime records this family without special-case trace logic:

- generator start/end or skip reason;
- every proposed transform tuple;
- every demonstration execution and fit decision;
- hidden execution outcomes;
- output-equivalence classes;
- final acceptance or ambiguity.

Compact and mechanistic modes must remain exactly identical after removal of the trace envelope.

## Testing

Strict TDD sequence:

1. add direct unit tests for representative quadrant arrangements and bounds;
2. add the nine immutable training fixtures and exact acceptance tests;
3. add a synthetic symmetry case where demonstrations support multiple transforms but the hidden input causes divergent outputs, requiring `AMBIGUOUS_PROGRAM`;
4. verify RED because `quadrant_mosaic` is absent;
5. implement the isolated module;
6. wire the interpreter and mechanistic generator;
7. run focused tests, the complete V2.2 cluster, frozen V2 integration tests, and the frozen-byte gate;
8. run all 1,000 ARC training tasks in compact and mechanistic modes;
9. require exactly the nine expected gains, no lost correct rows, no wrong accepts, one preserved ambiguity, 1,000 validated traces, and 1,000 parity matches;
10. publish and independently checksum the corpus artifact.

## Scope exclusions

This unit does not add arbitrary quadrant coloring, separators, overlays, repeated tiling, learned transform preference, task-ID routing, or public-evaluation tuning. Those are separate grammar families and require independent evidence and TDD cycles.
