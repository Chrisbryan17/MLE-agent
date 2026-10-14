"""Post-evaluation independent read-only integrity and seed-grouping audit.

This does not change the preregistered runner, predictions, labels or first score.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(root):
    root = Path(root)
    seal=json.loads((root/'commitments.json').read_text())
    assert sha(root/'public.json')==seal['public_sha256']
    assert sha(root/'sealed_labels.json')==seal['label_commitment_sha256']
    report=json.loads((root/'score.json').read_text())
    assert sha(root/'predictions.json')==report['predictions_sha256']
    public=json.loads((root/'public.json').read_text())
    labels=json.loads((root/'sealed_labels.json').read_text())['holdout_labels']
    rows=json.loads((root/'predictions.json').read_text())['predictions']
    assert len(rows)==seal['holdout_cases']==len(labels)==300
    assert len(public['train'])==seal['train_cases']==420
    assert len(set(r['id'] for r in rows))==300
    assert set(r['id'] for r in rows)==set(labels)
    assert max(c['shortest_hops'] for c in public['train']) <= 2
    assert min(c['shortest_hops'] for c in public['holdout']) >= 4
    assert all(r['holonomy']['prediction']==r['dsl']['prediction'] for r in rows)
    by_seed=defaultdict(list)
    for r in rows:
        serial=int(r['id'].split('-')[0]); seed=(serial-50000)//100000
        assert seed in seal['seed_streams']
        by_seed[seed].append(r)
    details={}
    for seed,items in sorted(by_seed.items()):
        correct={m:sum(r[m]['prediction'] is not None and r[m]['prediction']==labels[r['id']] for r in items)
                 for m in ('holonomy','dsl','graph','learned')}
        details[str(seed)]={"n":len(items),"correct":correct,
                            "holonomy_minus_graph_pp":round(100*(correct['holonomy']-correct['graph'])/len(items),2),
                            "heldout_hops":dict(sorted(Counter(r['shortest_hops'] for r in items).items()))}
        assert len(items)==100
    overall={m:sum(r[m]['prediction'] is not None and r[m]['prediction']==labels[r['id']] for r in rows)
             for m in report['results']}
    assert all(overall[m]==report['results'][m]['correct'] for m in overall)
    audit={"original_first_score_sha256":sha(root/'score.json'),
           "prediction_seal_sha256":sha(root/'predictions.json'),
           "all_300_holonomy_dsl_predictions_identical":True,
           "per_seed_corrected":details,
           "corrected_superiority_gate":False,
           "original_score_defect":"experiment.py scorer block selector groups only the first case of each seed: string prefix uses the complete start-case ID. Original reported per_seed_effects=[0,0,0] is invalid. Correct per-seed effects are [-0.10,-0.06,-0.06].",
           "interpretation":"Reporting erratum only. Frozen original scoring implementation and score.json retained unchanged."}
    output=root/'audit_addendum.json'
    if output.exists(): raise RuntimeError('refuse to overwrite audit')
    output.write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n')
    print(json.dumps(audit,sort_keys=True))

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python audit.py evidence/pilot-001')
    main(sys.argv[1])
