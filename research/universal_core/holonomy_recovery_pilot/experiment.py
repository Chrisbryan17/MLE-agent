"""Preregistered synthetic affine-transport OOD pilot. No ARC data or V2 edits.

Dependencies: Python 3.10+ standard library. Run 'python experiment.py --help'.
The evaluation labels are only read by 'score', never by 'predict'.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time

P = 11
PATH_BUDGET = 32
HOP_BUDGET = 7
SEEDS = (8101, 8102, 8103)
METHODS = ("holonomy", "dsl", "graph", "learned", "no_composition", "random_transport")


def canon(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value):
    return hashlib.sha256(canon(value)).hexdigest()


def inv(x):
    a, b = x
    ai = pow(a, -1, P)
    return (ai, (-ai * b) % P)


def comp(after, before):
    a, b = after
    c, d = before
    return ((a * c) % P, (a * d + b) % P)


def identity():
    return (1, 0)


def true_map(gauges, s, t):
    return comp(gauges[t], inv(gauges[s]))


def connected_distance(n, edges, s, t):
    q = deque([(s, 0)])
    visited = {s}
    while q:
        u, d = q.popleft()
        if u == t:
            return d
        for a, b, *_ in edges:
            v = b if a == u else a if b == u else None
            if v is not None and v not in visited:
                visited.add(v)
                q.append((v, d + 1))
    raise AssertionError("ring must be connected")


def make_case(seed, heldout, corruption):
    rng = random.Random(seed)
    n = 13 if heldout else 8
    gauges = [(rng.randrange(1, P), rng.randrange(P)) for _ in range(n)]
    pairs = {(i, i + 1) for i in range(n - 1)}
    pairs.add((0, n - 1))
    for i in range(n - 2):
        if rng.random() < (0.18 if heldout else 0.35):
            pairs.add((i, i + 2))
    edges = []
    for u, v in sorted(pairs):
        a, b = true_map(gauges, u, v)
        if rng.random() < corruption:
            if rng.randrange(2):
                a = (a % (P - 1)) + 1
            else:
                b = (b + rng.randrange(1, P)) % P
            if (a, b) == true_map(gauges, u, v):
                b = (b + 1) % P
        edges.append((u, v, a, b))
    choices = [(s, t) for s in range(n) for t in range(s + 1, n)
               if (connected_distance(n, edges, s, t) >= 4 if heldout
                   else connected_distance(n, edges, s, t) <= 2)]
    if not choices:
        raise AssertionError("no eligible query")
    s, t = rng.choice(choices)
    # Per-case relabelling prevents node-identifier lookup; labels never enter predictions.
    names = [f"n{rng.getrandbits(40):010x}" for _ in range(n)]
    observed = {"id": f"{seed}-{int(heldout)}-{int(corruption*100)}",
                "n": n, "edges": [[names[u], names[v], a, b] for u, v, a, b in edges],
                "source": names[s], "target": names[t],
                "regime": f"{'unseen_long' if heldout else 'development_short'}_noise{int(100*corruption)}",
                "shortest_hops": connected_distance(n, edges, s, t)}
    return observed, list(true_map(gauges, s, t))


def paths(case):
    adj = defaultdict(list)
    for u, v, a, b in case["edges"]:
        fwd = (a, b)
        adj[u].append((v, fwd))
        adj[v].append((u, inv(fwd)))
    for u in adj:
        adj[u].sort(key=lambda pair: pair[0])
    q = deque([(case["source"], frozenset([case["source"]]), identity(), 0)])
    found = []
    while q and len(found) < PATH_BUDGET:
        u, visited, program, steps = q.popleft()
        if u == case["target"]:
            found.append((program, steps))
            continue
        if steps >= HOP_BUDGET:
            continue
        for v, map_uv in adj[u]:
            if v not in visited:
                q.append((v, visited | {v}, comp(map_uv, program), steps + 1))
    return found


def support(paths_found):
    counts = Counter(m for m, _ in paths_found)
    minimum = {}
    for m, d in paths_found:
        minimum[m] = min(minimum.get(m, 100), d)
    return counts, minimum


def features(map_, found):
    counts, mins = support(found)
    n = max(1, len(found))
    c = counts[map_]
    weighted = sum(1 / d for m, d in found if m == map_)
    return (c / n, 1 / mins[map_], weighted / n)


def learn(train_cases, labels):
    """Supervised affine-program ranker, with train-only cross-entropy SGD."""
    records = []
    for c in train_cases:
        found = paths(c)
        if not found:
            continue
        choices = sorted({m for m, _ in found})
        target = tuple(labels[c["id"]])
        if target in choices:
            records.append((choices, [features(m, found) for m in choices], choices.index(target)))
    weights = [0.0, 0.0, 0.0]
    for _ in range(40):
        for _, vectors, correct in records:
            scores = [sum(w*x for w, x in zip(weights, vec)) for vec in vectors]
            high = max(scores)
            z = [math.exp(s - high) for s in scores]
            probs = [v / sum(z) for v in z]
            gradients = [vectors[correct][i] - sum(p*vec[i] for p,vec in zip(probs, vectors)) for i in range(3)]
            for i in range(3):
                weights[i] += 0.12 * gradients[i]
    return weights, len(records)


def choose(case, method, weights):
    found = paths(case)
    if not found:
        return None, 0.0, 0, 0
    if method == "no_composition":
        direct = [(m, d) for m, d in found if d == 1]
        return (list(direct[0][0]), 1., len(found), 1) if direct else (None, 0., len(found), 0)
    if method == "graph":
        return list(found[0][0]), 1., len(found), len(found)
    if method == "random_transport":
        rng = random.Random(int(hashlib.sha256(case["id"].encode()).hexdigest(), 16))
        found = [(((m[0], (m[1]+1) % P) if rng.random() < 0.2 else m),d) for m,d in found]
    counts, mins = support(found)
    if method == "holonomy":
        # Exact closed-loop residual H_ij = T_j^-1 o T_i; a loop closes iff H_ij = I.
        # With exact finite-group maps, maximizing zero residuals equals plurality vote.
        scores = {m: sum(comp(inv(n), m) == identity() for n, _ in found) for m in counts}
        cost = len(scores) * len(found)
    elif method == "learned":
        scores = {m: sum(w*x for w, x in zip(weights, features(m, found))) for m in counts}
        cost = len(counts) * len(found)
    else:
        # Ordinary finite DSL enumerator scores candidate affine programs against
        # identical path-derived demonstrations: T(x) at x=0,1.
        scores = {m: sum((m[1] == n[1] and (m[0]+m[1])%P == (n[0]+n[1])%P)
                         for n, _ in found) for m in counts}
        cost = len(counts) * len(found) * 2
    best = max(scores.values())
    winners = [m for m in scores if abs(scores[m] - best) < 1e-10]
    confidence = counts[min(winners)] / len(found)
    if len(winners) != 1:
        return None, confidence, len(found), cost
    return list(winners[0]), confidence, len(found), cost


def ensure_new_folder(path):
    path.mkdir(parents=True, exist_ok=False)


def prepare(root):
    ensure_new_folder(root)
    train_cases, train_labels, hold_cases, hold_labels = [], {}, [], {}
    for trial_seed in SEEDS:
        for j in range(140):
            noise = 0 if j % 2 == 0 else .15
            c, label = make_case(trial_seed * 100000 + j, False, noise)
            train_cases.append(c)
            train_labels[c["id"]] = label
        for j in range(100):
            noise = 0 if j % 2 == 0 else .15
            c, label = make_case(trial_seed * 100000 + 50000 + j, True, noise)
            hold_cases.append(c)
            hold_labels[c["id"]] = label
    # Holdout labels are written to a separate file; prediction stage never reads it.
    public = {"protocol": "affine_transport_ood_pilot_1", "path_budget": PATH_BUDGET,
              "train": train_cases, "train_labels": train_labels, "holdout": hold_cases}
    private = {"holdout_labels": hold_labels}
    (root / "public.json").write_bytes(canon(public))
    (root / "sealed_labels.json").write_bytes(canon(private))
    manifest = {"public_sha256": hashlib.sha256(canon(public)).hexdigest(),
                "label_commitment_sha256": hashlib.sha256(canon(private)).hexdigest(),
                "train_cases": len(train_cases), "holdout_cases": len(hold_cases), "seed_streams": SEEDS,
                "authoritative_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root / "commitments.json").write_bytes(canon(manifest))
    print(json.dumps(manifest, sort_keys=True))


def predict(root):
    if (root / "predictions.json").exists() or (root / "score.json").exists():
        raise RuntimeError("already predicted/scored; refuse overwrite")
    pub_bytes = (root / "public.json").read_bytes()
    manifest = json.loads((root / "commitments.json").read_text())
    if hashlib.sha256(pub_bytes).hexdigest() != manifest["public_sha256"]:
        raise RuntimeError("public payload changed")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["authoritative_code_sha256"]:
        raise RuntimeError("candidate implementation differs from preregistered file")
    public = json.loads(pub_bytes)
    weights, fit_count = learn(public["train"], public["train_labels"])
    outputs = []
    for case in public["holdout"]:
        record = {"id": case["id"], "regime": case["regime"], "shortest_hops": case["shortest_hops"]}
        for method in METHODS:
            start = time.perf_counter_ns()
            prediction, confidence, count, ops = choose(case, method, weights)
            latency_ns = time.perf_counter_ns() - start
            record[method] = {"prediction": prediction, "confidence": confidence,
                              "paths": count, "operations": ops, "latency_ns": latency_ns}
        outputs.append(record)
    output = {"protocol": public["protocol"], "weights": weights, "fit_count": fit_count,
              "public_sha256": manifest["public_sha256"], "predictions": outputs}
    (root / "predictions.json").write_bytes(canon(output))
    print(json.dumps({"prediction_sha256": hashlib.sha256(canon(output)).hexdigest(),
                      "cases": len(outputs), "fit_count": fit_count, "weights": weights}))


def wilson(k,n):
    if n == 0: return [0., 1.]
    z=1.959963984540054
    p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [round(center-half, 4), round(center+half, 4)]


def binomial_p_two_sided(a,b):
    n = a+b
    if n == 0: return 1.
    tail = sum(math.comb(n, j) for j in range(min(a,b)+1)) / (2**n)
    return min(1., 2*tail)


def score(root):
    if (root / "score.json").exists(): raise RuntimeError("already scored; refuse overwrite")
    manifest = json.loads((root / "commitments.json").read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["authoritative_code_sha256"]:
        raise RuntimeError("scorer file differs from preregistered candidate")
    public_bytes=(root / "public.json").read_bytes()
    if hashlib.sha256(public_bytes).hexdigest() != manifest["public_sha256"]:
        raise RuntimeError("public payload changed")
    private_bytes=(root / "sealed_labels.json").read_bytes()
    if hashlib.sha256(private_bytes).hexdigest() != manifest["label_commitment_sha256"]:
        raise RuntimeError("sealed labels changed")
    prediction_bytes=(root / "predictions.json").read_bytes()
    sealed_prediction_sha=hashlib.sha256(prediction_bytes).hexdigest()
    pred=json.loads(prediction_bytes)
    labels=json.loads(private_bytes)["holdout_labels"]
    if len(pred["predictions"]) != len(labels): raise RuntimeError("prediction count mismatch")
    if {r["id"] for r in pred["predictions"]} != set(labels): raise RuntimeError("IDs mismatch")
    results={}
    correctness={}
    for method in METHODS:
        rows=pred["predictions"]
        yes=[r[method]["prediction"] is not None and r[method]["prediction"] == labels[r["id"]] for r in rows]
        accepted=[r[method]["prediction"] is not None for r in rows]
        n=len(rows); a=sum(accepted); c=sum(yes)
        groups={}
        for family in sorted({r["regime"] for r in rows}):
            indices=[i for i,r in enumerate(rows) if r["regime"]==family]
            groups[family]={"correct":sum(yes[i] for i in indices),"n":len(indices),
                            "accuracy":round(sum(yes[i] for i in indices)/len(indices),4)}
        confidences=[r[method]["confidence"] for r in rows]
        brier=sum((float(cf)-int(ok))**2 for cf,ok in zip(confidences,yes))/n
        ranked=sorted(range(n),key=lambda i:(-confidences[i],rows[i]["id"]))
        risk_curve={str(frac):round(1-sum(yes[i] for i in ranked[:max(1,int(frac*n))]) / max(1,int(frac*n)),4)
                    for frac in (.25,.5,.75,1.)}
        results[method]={"correct":c,"accepted":a,"wrong_accepted":a-c,"n":n,
                         "accuracy":round(c/n,4),"coverage":round(a/n,4),
                         "selective_accuracy":round(c/a,4) if a else None,
                         "accuracy_wilson_95":wilson(c,n),"per_regime":groups,
                         "brier":round(brier,5),"risk_at_coverage":risk_curve,
                         "median_latency_ns":int(statistics.median(r[method]["latency_ns"] for r in rows)),
                         "mean_operations":round(statistics.mean(r[method]["operations"] for r in rows),2)}
        correctness[method]=yes
    comparisons={}
    for baseline in METHODS:
        if baseline=="holonomy":continue
        x=correctness["holonomy"]; y=correctness[baseline]
        wins=sum(a and not b for a,b in zip(x,y)); losses=sum(b and not a for a,b in zip(x,y))
        comparisons[baseline]={"holonomy_minus_baseline_accuracy":round((wins-losses)/len(x),4),
                               "holonomy_only_correct":wins,"baseline_only_correct":losses,
                               "mcnemar_exact_p_two_sided":round(binomial_p_two_sided(wins,losses),6)}
    # Criterion: gain >=5 pp vs strongest non-holonomy, no loss on any stream,
    # and a 95% paired bootstrap lower CI > 0; otherwise no demonstrated advantage.
    rows=pred["predictions"]; strongest=max((m for m in METHODS if m!="holonomy"),key=lambda m:results[m]["accuracy"])
    differences=[int(a)-int(b) for a,b in zip(correctness["holonomy"],correctness[strongest])]
    rng=random.Random(700700)
    boots=[]
    for _ in range(4000):
        boots.append(sum(differences[rng.randrange(len(rows))] for _ in rows)/len(rows))
    boots.sort()
    low,high=boots[100], boots[3899]
    blocks=[]
    for seed in SEEDS:
        ids=[i for i,r in enumerate(rows) if r["id"].startswith(str(seed*100000 + 50000)[:])]
        # Numeric task IDs occupy a contiguous block for each stream.
        if not ids: raise RuntimeError("missing stream")
        blocks.append(round(sum(differences[i] for i in ids)/len(ids),4))
    delta=results["holonomy"]["accuracy"]-results[strongest]["accuracy"]
    decision={"strongest_non_holonomy":strongest,"delta":round(delta,4),
              "paired_bootstrap_95":[round(low,4),round(high,4)],"per_seed_effects":blocks,
              "holonomy_superiority_supported":bool(delta>=.05 and low>0 and all(x>=0 for x in blocks)),
              "interpretation":"synthetic oracle-graph affine-composition pilot only; no ARC/unrestricted semantic transfer claim"}
    report={"protocol":pred["protocol"],"predictions_sha256":sealed_prediction_sha,
            "label_commitment_sha256":manifest["label_commitment_sha256"],
            "results":results,"paired":comparisons,"decision":decision}
    (root / "score.json").write_bytes(canon(report))
    print(json.dumps({"decision":decision,"accuracy":{k:v["accuracy"] for k,v in results.items()},
                      "prediction_sha256":sealed_prediction_sha},sort_keys=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("prepare","predict","score"))
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    {"prepare":prepare,"predict":predict,"score":score}[args.phase](args.out)

if __name__=="__main__":main()