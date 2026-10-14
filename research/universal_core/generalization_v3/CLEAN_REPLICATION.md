# NNN Pilot 003: Clean-Seed Replication Preregistration

**Date:** 2026-10-14, before any evaluation-label generation or scoring on these seeds. **Parent branch:** `research/nnn-v3-generalization-recovery-20261014` at `110d21462f23976ede5abaddfc0d5e734e270705`. **Target branch:** `research/nnn-v3-clean-replication-20261014`.

## Why a replication is necessary

Pilot 002 was correctly committed in source/data/query/prediction order, but its frozen unit test also regenerated and scored the same fixed-seed tasks in a temporary directory. These intermediate labels were not inspected, yet this invalidated a claim of a strictly unexposed holdout. The original results, including its negative superiority gate, are retained untouched. This experiment repairs the unit-test seed isolation and measures newly generated tasks once. No algorithm parameter, grammar, library ranking or search/query budget is changed from Pilot 002.

## Frozen changes and data

1. Only the evaluation seed tuple in `experiment.py` changes to **(10103, 10111, 10141)** and the protocol string changes to `v3-active-composition-002`. Method implementations, learning algorithm, candidate ordering, limits, query-selection criteria, score logic and threshold are otherwise byte-equivalent to Pilot 002.
2. Tests are amended to patch `experiment.SEEDS` to **(3331, 3337, 3343)** before *all* generator and score calls, ensuring no unit test ever generates the official Pilot 003 evaluation seeds. Never run a development test that scores the official seeds before the committed first attempt.
3. Train: 36 two-operation problems per stream, four demonstrations each (108 total). Evaluation: 60 unseen-signature length-three composition cases per stream, one demonstration each (180 total), with a 12-query input pool. Synthetic finite-vector `Z/7Z` data; no external ARC tasks.
4. Pre-committed sequential SHA-256s for public inputs, hidden targets and query oracle; a separate *public-only* query proposal, sealed and committed prior to feedback; exactly one released oracle query answer per method; first predictions committed before exposing test labels. Scripts refuse overwrite.

## Frozen methods, metrics and decision gate

Methods and budget exactly Pilot 002: `no_query`, `random_query`, `active_query`, `active_no_macros`, `full_no_query`, `active_full`. Search cap 52 for limited methods and complete 66-candidate enumeration for full. One external oracle answer for every query-using method. Confidence derived from candidate vote fractions, not calibrated probabilities. 

**Primary null:** no positive active-query improvement over matched random querying. **Primary gate:** raw exact accuracy gain at least +5 percentage points; paired 3,000-resample bootstrap 95% lower bound strictly greater than 0; active method no worse than random on any of three streams. Report exact correct/accepted/wrong counts, coverage, attempted accuracy, Wilson 95%, bootstrap effect, exact McNemar, all ablations, and per-seed effects. No repairs based on scored errors; if gate fails, stop and report null/inconclusive outcome.

**Important limits:** These are internally generated, algorithmically easy tasks from a *known* fixed primitive library; this cannot demonstrate unseen primitive invention, open-world semantic compilation, real-world OOD generality, scientific novelty or frontier-level reasoning. Unit-test-seed separation restores the internal first-attempt separation, not an external administering party. A second independent high-quality benchmark and real semantically grounded input are still missing.
