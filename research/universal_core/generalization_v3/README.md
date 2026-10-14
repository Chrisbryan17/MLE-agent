# NNN v3 Generalization Research (Pilot 002)

A bounded, source-available *research testbed*. Not a universal reasoning system, not ARC-AGI performance, and not a trained world-to-graph model.

- `synthesis.py`: finite compositional program interpreter, behavior deduplication, demonstration-derived macros, posterior-version-space selection, outcome-entropy active experiment choice, ambiguity-aware answers.
- `semantics.py`: typed, evidence-grounded semantic fact contract, temporal and logical scope validation, extraction metrics, existential question answering with contradiction-aware abstention.
- `transport.py`: finite modular synchronization with cycle residuals, graph-tree and robust edge-disagreement baseline.
- `experiment.py`: reproducible separated train/evaluation generation, sealed oracle-query feedback, irreversible first-attempt predictions and guarded scoring.
- `tests/test_v3.py`: checks arithmetic, noncommutation, split integrity, leak barriers, source provenance, temporal scoping and negative cases.

Python 3.10+ standard library. From this folder:

```sh
python -m unittest discover -s tests -v
python experiment.py prepare --out evidence/pilot-002
python experiment.py queries --out evidence/pilot-002
# Commit query_sha256 before querying oracle:
python experiment.py feedback --out evidence/pilot-002 --query-sha256 <committed-digest>
python experiment.py predict --out evidence/pilot-002 --query-sha256 <committed-digest> --feedback-sha256 <verified-digest>
# Commit prediction_sha256 before scoring:
python experiment.py score --out evidence/pilot-002 --prediction-sha256 <committed-digest>
```

For another controlled replication, use a new directory and new frozen seed streams. Never retune against Pilot 002's opened labels. See `PREREGISTRATION.md` and `RESULTS.md` (after first score) for effect sizes and explicit limitations.
