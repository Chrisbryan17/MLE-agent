# NNN P004 obstruction diagnosis pilot

Run with Python 3.10+ (stdlib only):

```bash
python -m unittest discover -s tests -v
python experiment.py prepare evidence/holdout --count 40 --split holdout
python experiment.py plan evidence/holdout
python experiment.py broker evidence/holdout
python experiment.py predict evidence/holdout
python experiment.py score evidence/holdout
```

**Integrity:** `prepare` seals the target-label digest before predictions; `plan` and `predict` never read the sealed target file; `broker` exposes only the selected oracle measurements, without target labels; `score` is one-shot and checks all digests. This protocol alone does not provide strong human-blindness for synthetic generated labels. Do not tune after seeing confirmatory scores. Dev runs use different seeds and no confirmatory labels.

**Hypothesis boundaries:** This measures five *predefined* cause templates over a small finite field, not discovery of arbitrary programs or unrestricted semantics. A successful result would justify further work, not establish general intelligence or novelty.
