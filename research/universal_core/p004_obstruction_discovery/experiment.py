"""P004: obstruction-driven mechanism diagnosis under active interventions.

Synthetic evidence only. Standard-library Python >= 3.10.
No hidden labels are imported by request/predict. One oracle query per task.
No claim of operator invention: competing mechanisms are frozen in MODEL_FEATURES.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

P = 13
FEATURES = ("constant", "entity", "switch", "quadratic", "path")
METHODS = ("flat", "passive", "random", "entropy", "target_risk", "odmd", "odmd_no_quadratic", "odmd_no_switch")
SEEDS = (81091, 81092, 81093)
NOISE = {"constant": .18, "entity": .06, "switch": .06, "quadratic": .06, "path": .06}
# Fixed before confirmatory scoring. Rank bonus is modest; not a substitute for inference.
RANK_BONUS = 0.04


def canonical(value):
    return (json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(data))


def read_json(path):
    return json.loads(Path(path).read_text())


def feature(name, row):
    if name == "constant":
        return 0
    if name == "entity":
        return row["entity"]
    if name == "switch":
        return row["switch"]
    if name == "quadratic":
        return row["x"] ** 2 % P
    if name == "path":
        return row["path"]
    raise ValueError(name)


def result(name, a, b, row):
    return (row["x"] + a + b * feature(name, row)) % P


def candidates(excluded=()):
    return [(f, a, b) for f in FEATURES if f not in excluded for a in range(P)
            for b in (range(1, P) if f != "constant" else (0,))]


def rank_mod(rows):
    """Rank of contextual feature design over GF(13), not an inference guarantee."""
    mat = [[1, row["entity"], row["switch"], row["path"], row["x"] ** 2 % P]
           for row in rows]
    if not mat:
        return 0
    rank = 0
    for col in range(5):
        pivot = next((i for i in range(rank, len(mat)) if mat[i][col] % P), None)
        if pivot is None:
            continue
        mat[rank], mat[pivot] = mat[pivot], mat[rank]
        inv = pow(mat[rank][col], -1, P)
        mat[rank] = [(x * inv) % P for x in mat[rank]]
        for k in range(len(mat)):
            if k != rank:
                coeff = mat[k][col]
                mat[k] = [(u - coeff * v) % P for u, v in zip(mat[k], mat[rank])]
        rank += 1
        if rank == len(mat):
            break
    return rank


def make_row(x, e, s, p):
    return {"x": x, "entity": e, "switch": s, "path": p}


def make_dataset(seed, tasks_per_seed, *, split):
    rng = random.Random(seed)
    public = []
    private = []
    for i in range(tasks_per_seed):
        family = FEATURES[i % len(FEATURES)]
        a, b = rng.randrange(P), (rng.randrange(1, P) if family != "constant" else 0)
        demos = []
        for j in range(4 if split == "holdout" else 5):
            x = rng.choice((0, 1, 2, 3) if split == "holdout" else (0, 1, 2, 3, 4))
            confounded = rng.randrange(2)
            e = confounded if rng.random() < .83 else rng.randrange(2)
            s = confounded if rng.random() < .83 else rng.randrange(2)
            p = confounded if rng.random() < .83 else rng.randrange(2)
            row = make_row(x, e, s, p)
            y = result(family, a, b, row)
            if rng.random() < NOISE[family]:
                y = (y + rng.randrange(1, P)) % P
            demos.append({**row, "y": y})
        qs = [make_row(x, e, s, p) for x in range(9)
              for (e, s, p) in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))]
        rng.shuffle(qs)
        # Inputs of scored rows are visible. Outputs stay in sealed labels.
        targets = [make_row(rng.randrange(9, P), rng.randrange(2), rng.randrange(2), rng.randrange(2))
                   for _ in range(5)]
        key = f"{split}-{seed}-{i:04d}"
        public.append({"id": key, "demonstrations": demos, "queries": qs, "targets": targets})
        private.append({"id": key, "cause": family, "params": [a, b],
                        "targets": [result(family, a, b, t) for t in targets],
                        "query_y": [result(family, a, b, q) for q in qs]})
    return public, private


def posterior(demos, excluded=()):
    """Exact discrete Bayesian enumeration under a noisy modular generative model."""
    cs = candidates(excluded)
    if not cs:
        raise ValueError("no models")
    family_count = len({h[0] for h in cs})
    logs = []
    for fam, a, b in cs:
        size = P if fam == "constant" else P * (P - 1)
        score = -math.log(family_count * size)
        noise = NOISE[fam]
        for row in demos:
            ok = result(fam, a, b, row) == row["y"]
            score += math.log(1 - noise if ok else noise / (P - 1))
        logs.append(score)
    maxlog = max(logs)
    ws = [math.exp(x - maxlog) for x in logs]
    scale = sum(ws)
    return cs, [w / scale for w in ws]


def update_with_observation(cs, weights, query, observed):
    noise = .005  # protocol: targeted interventions are high-reliability repeats
    new = [(w * (1 - noise if result(*h, query) == observed else noise / (P - 1)))
           for h, w in zip(cs, weights)]
    total = sum(new)
    return [w / total for w in new]


def distribution(cs, ws, row):
    dist = [0.] * P
    for h, w in zip(cs, ws):
        dist[result(*h, row)] += w
    return dist


def classify(cs, ws):
    d = {f: 0.0 for f in FEATURES}
    for h, w in zip(cs, ws):
        d[h[0]] += w
    return max(FEATURES, key=lambda f: (d[f], -FEATURES.index(f)))


def predict_one(cs, ws, row):
    dist = distribution(cs, ws, row)
    return max(range(P), key=lambda k: (dist[k], -k))


def risk_gain(cs, ws, query, targets):
    """Expected improvement of Bayes decision accuracy across visible target inputs.

    In the planned noise-free partition calculation, the sum of masses of
    the best prediction in each query-answer cell equals expected accuracy.
    """
    before = sum(max(distribution(cs, ws, t)) for t in targets) / len(targets)
    improved = 0.0
    for t in targets:
        groups = [[0.] * P for _ in range(P)]
        for h, w in zip(cs, ws):
            groups[result(*h, query)][result(*h, t)] += w
        improved += sum(max(group) for group in groups) / len(targets)
    return improved - before


def entropy(dist):
    return -sum(w * math.log(w) for w in dist if w > 0)


def choose_query(method, cs, ws, task, rng):
    if method in ("flat", "passive"):
        return None
    queries = task["queries"]
    if method == "random":
        return rng.randrange(len(queries))
    before_rank = rank_mod(task["demonstrations"])
    best = (-float("inf"), 0)
    for i, query in enumerate(queries):
        if method == "entropy":
            score = entropy(distribution(cs, ws, query))
        else:
            score = risk_gain(cs, ws, query, task["targets"])
            if method.startswith("odmd"):
                gain = rank_mod(task["demonstrations"] + [query]) - before_rank
                score += RANK_BONUS * gain
        if score > best[0] + 1e-12:
            best = (score, i)
    return best[1]


def filter_models(method):
    return ("quadratic",) if method == "odmd_no_quadratic" else (("switch",) if method == "odmd_no_switch" else ())


def plan_requests(public):
    out = []
    for t in public:
        choices = {}
        for m in METHODS:
            if m == "flat":
                cs, ws = posterior(t["demonstrations"], excluded=tuple(f for f in FEATURES if f != "constant"))
            else:
                cs, ws = posterior(t["demonstrations"], excluded=filter_models(m))
            rng = random.Random(digest([t["id"], m, "random-probe"]))
            choices[m] = choose_query(m, cs, ws, t, rng)
        out.append({"id": t["id"], "requests": choices})
    return out


def issue_replies(public, labels, requests):
    """Oracle broker: releases only requested intervention observations, not cause/test labels."""
    lab = {x["id"]: x for x in labels}
    req = {x["id"]: x["requests"] for x in requests}
    out = []
    for t in public:
        truth, asks = lab[t["id"]], req[t["id"]]
        resp = {}
        for method in METHODS:
            idx = asks[method]
            resp[method] = None if idx is None else truth["query_y"][idx]
        out.append({"id": t["id"], "answers": resp})
    return out


def perform_prediction(public, requests, replies):
    req = {x["id"]: x["requests"] for x in requests}
    ans = {x["id"]: x["answers"] for x in replies}
    predictions = []
    for task in public:
        by_method = {}
        for method in METHODS:
            excluded = filter_models(method)
            if method == "flat":
                excluded = tuple(f for f in FEATURES if f != "constant")
            cs, ws = posterior(task["demonstrations"], excluded)
            idx = req[task["id"]][method]
            if idx is not None:
                answer = ans[task["id"]][method]
                if not type(answer) is int or not 0 <= answer < P:
                    raise ValueError("oracle answer invalid")
                ws = update_with_observation(cs, ws, task["queries"][idx], answer)
            by_method[method] = {"cause": classify(cs, ws),
                                 "predictions": [predict_one(cs, ws, t) for t in task["targets"]],
                                 "query_index": idx,
                                 "top_posterior": round(max(ws), 8)}
        predictions.append({"id": task["id"], "methods": by_method})
    return predictions


def paired_ci(rows, key_a, key_b, *, nboot=2000, seed=99189):
    """Cluster bootstrap over independent generated tasks, not over their five rows."""
    rng = random.Random(seed)
    v = [x[key_a] - x[key_b] for x in rows]
    if not v:
        return [0., 0.]
    means = []
    for _ in range(nboot):
        means.append(sum(v[rng.randrange(len(v))] for _ in v) / len(v))
    means.sort()
    return [round(means[int(.025 * nboot)], 6), round(means[int(.975 * nboot)], 6)]


def score(public, labels, requests, predictions):
    lmap = {x["id"]: x for x in labels}
    pmap = {x["id"]: x for x in predictions}
    rows = []
    for task in public:
        truth, predicted = lmap[task["id"]], pmap[task["id"]]
        item = {"id": task["id"], "family": truth["cause"]}
        for method in METHODS:
            pred = predicted["methods"][method]
            item[method] = sum(a == b for a, b in zip(pred["predictions"], truth["targets"])) / len(truth["targets"])
            item[method + "_diagnosis"] = int(pred["cause"] == truth["cause"])
        rows.append(item)
    family_scores = {f: {m: round(statistics.mean(x[m] for x in rows if x["family"] == f), 6)
                         for m in METHODS} for f in FEATURES if any(x["family"] == f for x in rows)}
    scores = {m: {"accuracy": round(statistics.mean(x[m] for x in rows), 6),
                  "diagnosis": round(statistics.mean(x[m + "_diagnosis"] for x in rows), 6)}
              for m in METHODS}
    gate = max(scores[m]["accuracy"] for m in ("flat", "passive", "random", "entropy", "target_risk"))
    uplift = scores["odmd"]["accuracy"] - gate
    ci = paired_ci(rows, "odmd", max(("flat", "passive", "random", "entropy", "target_risk"), key=lambda m: scores[m]["accuracy"]))
    return {"cases": len(rows), "metrics": scores, "family": family_scores,
            "odmd_gain_vs_strongest_baseline": round(uplift, 6),
            "paired_95pct_ci": ci,
            "preregistered_superiority": bool(uplift >= .05 and ci[0] > 0),
            "per_seed": {str(s): {m: round(statistics.mean(row[m] for row in rows if row["id"].split("-")[1] == str(s)), 6)
                                    for m in METHODS} for s in SEEDS if any(row["id"].split("-")[1] == str(s) for row in rows)},
            "note": "Synthetic, predefined hypothesis families; not novel operator invention."}


def cmd_prepare(args):
    if any((Path(args.directory) / x).exists() for x in ("public.json", "sealed_private.json")):
        raise FileExistsError("prepare is one-shot; use a new output directory")
    public, hidden = [], []
    for seed in SEEDS:
        p, h = make_dataset(seed, args.count, split=args.split)
        public.extend(p)
        hidden.extend(h)
    d = Path(args.directory)
    write_json(d / "public.json", public)
    write_json(d / "sealed_private.json", hidden)
    write_json(d / "commitment.json", {"public_sha256": digest(public), "private_sha256": digest(hidden),
                                        "seeds": list(SEEDS), "cases": len(public), "split": args.split})
    print("Prepared sealed cases:", len(public), "private commitment:", digest(hidden))


def cmd_plan(args):
    d = Path(args.directory)
    public = read_json(d / "public.json")
    commitment = read_json(d / "commitment.json")
    if digest(public) != commitment["public_sha256"]:
        raise ValueError("public digest mismatch")
    requests = plan_requests(public)
    write_json(d / "requests.json", requests)
    print("Query plan sealed", digest(requests))


def cmd_broker(args):
    d = Path(args.directory)
    if (d / "replies.json").exists():
        raise FileExistsError("oracle broker is one-shot")
    labels = read_json(d / "sealed_private.json")
    commit = read_json(d / "commitment.json")
    if digest(labels) != commit["private_sha256"]:
        raise ValueError("sealed labels tampered")
    req = read_json(d / "requests.json")
    write_json(d / "replies.json", issue_replies(read_json(d / "public.json"), labels, req))
    print("Only selected query observations released")


def cmd_predict(args):
    d = Path(args.directory)
    if (d / "predictions.json").exists():
        raise FileExistsError("prediction seal is one-shot")
    pub, req, resp = [read_json(d / p) for p in ("public.json", "requests.json", "replies.json")]
    predictions = perform_prediction(pub, req, resp)
    write_json(d / "predictions.json", predictions)
    write_json(d / "prediction_seal.json", {"public_sha256": digest(pub), "requests_sha256": digest(req),
                                                   "replies_sha256": digest(resp),
                                                   "predictions_sha256": digest(predictions)})
    print("Predictions sealed", digest(predictions))


def cmd_score(args):
    d = Path(args.directory)
    if (d / "score.json").exists():
        raise FileExistsError("score-once gate")
    commit, seal = read_json(d / "commitment.json"), read_json(d / "prediction_seal.json")
    pub, hidden, req, resp, pred = [read_json(d / p) for p in
                                   ("public.json", "sealed_private.json", "requests.json", "replies.json", "predictions.json")]
    for expected, actual in ((commit["public_sha256"], digest(pub)),
                             (commit["private_sha256"], digest(hidden)),
                             (seal["predictions_sha256"], digest(pred)),
                             (seal["requests_sha256"], digest(req)),
                             (seal["replies_sha256"], digest(resp))):
        if expected != actual:
            raise ValueError("sha256 provenance gate failed")
    report = score(pub, hidden, req, pred)
    report["commitment_sha256"] = digest(commit)
    report["prediction_seal_sha256"] = digest(seal)
    write_json(d / "score.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("prepare", "plan", "broker", "predict", "score"):
        cmd = sub.add_parser(action)
        cmd.add_argument("directory")
        if action == "prepare":
            cmd.add_argument("--count", type=int, default=40)
            cmd.add_argument("--split", choices=("development", "holdout"), default="holdout")
    args = p.parse_args()
    {"prepare": cmd_prepare, "plan": cmd_plan, "broker": cmd_broker,
     "predict": cmd_predict, "score": cmd_score}[args.action](args)


if __name__ == "__main__":
    main()
