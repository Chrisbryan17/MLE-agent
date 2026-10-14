"""Sealed, single-attempt active compositional induction pilot (standard library only).

Commands MUST be run in prepare -> queries -> feedback -> predict -> score order.
The optional feedback file contains answers to only the previously selected queries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

from synthesis import (
    canonical, canonical_programs, choose_active, consensus, digest,
    fit, infer, learn_library, order_candidates, run, signature,
)

SEEDS = (9173, 9179, 9187)
TRAIN_PER_SEED = 36
TEST_PER_SEED = 60
BUDGET = 52
POOL_SIZE = 12
N_QUERIES = 1
METHODS = ("no_query", "random_query", "active_query", "active_no_macros", "full_no_query", "active_full")
MAX_EVAL = 3


def dump(path: Path, data: object) -> None:
    if path.exists():
        raise FileExistsError(f"sealed output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(data))


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def randvec(rng: random.Random) -> list[int]:
    return [rng.randrange(7) for _ in range(4)]


def generate() -> tuple[dict, dict, dict]:
    train_programs = canonical_programs(2)
    train_programs = [p for p in train_programs if len(p) == 2]
    train_signatures = {signature(p) for p in canonical_programs(2)}
    test_programs = [p for p in canonical_programs(3) if len(p) == 3 and signature(p) not in train_signatures]
    if not train_programs or not test_programs:
        raise AssertionError("empty split")
    public = {"protocol": "v3-active-composition-001", "seeds": list(SEEDS), "budget": BUDGET,
              "train": [], "holdout": [], "holdout_length": 3, "train_length": 2,
              "operator_set": ["roll", "reverse", "inc_first", "inc_last", "swap_mid"]}
    gold, feedback = {}, {}
    for seed in SEEDS:
        rng = random.Random(seed)
        for idx in range(TRAIN_PER_SEED):
            prog = train_programs[rng.randrange(len(train_programs))]
            demos = []
            for _ in range(4):
                x = randvec(rng)
                demos.append({"input": x, "output": list(run(prog, x))})
            public["train"].append({"id": f"train-{seed}-{idx:03d}", "demos": demos})
        for idx in range(TEST_PER_SEED):
            prog = test_programs[rng.randrange(len(test_programs))]
            demos = []
            for _ in range(1):
                x = randvec(rng)
                demos.append({"input": x, "output": list(run(prog, x))})
            pool = [randvec(rng) for _ in range(POOL_SIZE)]
            test_input = randvec(rng)
            key = f"holdout-{seed}-{idx:03d}"
            public["holdout"].append({"id": key, "demos": demos, "pool": pool, "test_input": test_input})
            gold[key] = {"test_output": list(run(prog, test_input)), "regime": "length3_unseen_signature", "seed": seed}
            feedback[key] = [list(run(prog, q)) for q in pool]
    return public, gold, feedback


def verify_files(out: Path, *keys: str) -> dict:
    commitments = load(out / "commitments.json")
    for key in keys:
        if file_sha(out / key) != commitments["sha256"][key]:
            raise RuntimeError("SHA mismatch: " + key)
    return commitments


def prepare(out: Path) -> dict:
    public, gold, feedback = generate()
    for path, obj in (("public.json", public), ("sealed_test_labels.json", gold), ("sealed_query_oracle.json", feedback)):
        dump(out / path, obj)
    paths = ["public.json", "sealed_test_labels.json", "sealed_query_oracle.json"]
    commit = {"protocol": public["protocol"], "seeds": list(SEEDS), "train": len(public["train"]),
              "holdout": len(public["holdout"]), "operators": public["operator_set"],
              "sha256": {p: file_sha(out / p) for p in paths}, "budget": BUDGET,
              "query_limit": N_QUERIES, "source_sha256": {p: file_sha(Path(__file__).parent / p)
                      for p in ("experiment.py", "synthesis.py", "semantics.py")}}
    dump(out / "commitments.json", commit)
    return commit


def random_index(key: str, pool: list) -> int:
    return int(digest({"id": key, "salt": "passive_query_control"})[:12], 16) % len(pool)


def query_choices(out: Path) -> dict:
    verify_files(out, "public.json")
    public = load(out / "public.json")
    library = learn_library(public["train"])
    grammar = canonical_programs(MAX_EVAL)
    limited = order_candidates(grammar, library)
    decisions = {}
    for task in public["holdout"]:
        fitting = fit(task["demos"], limited, BUDGET)
        fitting_plain = fit(task["demos"], grammar, BUDGET)
        choices = {"random_query": random_index(task["id"], task["pool"]),
                   "active_query": choose_active(fitting, task["pool"]),
                   "active_no_macros": choose_active(fitting_plain, task["pool"]),
                   "active_full": choose_active(fit(task["demos"], grammar, len(grammar)), task["pool"])}
        decisions[task["id"]] = choices
    dump(out / "queries.json", decisions)
    return {"query_digest": file_sha(out / "queries.json"), "n": len(decisions),
            "learned_macro_count": len(library.macros), "macro_support": list(library.support),
            "train_digest": library.training_digest}


def release_feedback(out: Path, *, expected_query_sha256: str) -> dict:
    verify_files(out, "public.json", "sealed_query_oracle.json")
    if file_sha(out / "queries.json") != expected_query_sha256:
        raise RuntimeError("query choices must be externally sealed before feedback release")
    choices = load(out / "queries.json")
    oracle = load(out / "sealed_query_oracle.json")
    data = {}
    for taskid, indices in choices.items():
        data[taskid] = {}
        for method, index in indices.items():
            if type(index) is not int or not 0 <= index < POOL_SIZE:
                raise ValueError("invalid query index")
            data[taskid][method] = oracle[taskid][index]
    dump(out / "feedback.json", data)
    return {"feedback_sha256": file_sha(out / "feedback.json")}


def predict(out: Path, *, expected_query_sha256: str, expected_feedback_sha256: str) -> dict:
    verify_files(out, "public.json")
    if file_sha(out / "queries.json") != expected_query_sha256 or file_sha(out / "feedback.json") != expected_feedback_sha256:
        raise RuntimeError("unsealed query or feedback payload")
    public = load(out / "public.json")
    library = learn_library(public["train"])
    grammar = canonical_programs(MAX_EVAL)
    limited = order_candidates(grammar, library)
    queries = load(out / "queries.json")
    feedback = load(out / "feedback.json")
    results = {}
    for task in public["holdout"]:
        k = task["id"]
        results[k] = {"no_query": infer(task, limited, BUDGET),
                      "full_no_query": infer(task, grammar, len(grammar))}
        for m in ("random_query", "active_query", "active_no_macros", "active_full"):
            cand = grammar if m in ("active_no_macros", "active_full") else limited
            budget = len(grammar) if m == "active_full" else BUDGET
            results[k][m] = infer(task, cand, budget, query_index=queries[k][m], feedback=feedback[k][m])
    dump(out / "predictions.json", results)
    return {"prediction_sha256": file_sha(out / "predictions.json"), "program_count": len(grammar),
            "macro_count": len(library.macros), "results": len(results)}


def wilson(correct: int, n: int) -> list[float]:
    if not n:
        return [0, 1]
    z = 1.959963984540054
    p = correct / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    margin = z * math.sqrt((p * (1 - p) + z*z/(4*n))/n) / d
    return [center-margin, center+margin]


def paired_effect(predictions: dict, gold: dict, left: str, right: str) -> dict:
    """Paired confidence interval and exact McNemar test; no unpaired approximation."""
    keys = sorted(gold)
    x = [int(predictions[k][left]["status"] == "ACCEPTED" and
             predictions[k][left]["prediction"] == gold[k]["test_output"]) for k in keys]
    y = [int(predictions[k][right]["status"] == "ACCEPTED" and
             predictions[k][right]["prediction"] == gold[k]["test_output"]) for k in keys]
    wins = sum(a and not b for a, b in zip(x, y))
    losses = sum(b and not a for a, b in zip(x, y))
    n = len(keys)
    rng = random.Random(20261014)
    bootstrap = []
    for _ in range(3000):
        bootstrap.append(sum(x[i] - y[i] for i in (rng.randrange(n) for _ in range(n))) / n)
    bootstrap.sort()
    discordant = wins + losses
    pvalue = min(1., 2. * sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1)) / (2 ** discordant)) if discordant else 1.
    return {"left": left, "right": right, "effect": (sum(x)-sum(y))/n,
            "paired_bootstrap_95": [bootstrap[74], bootstrap[2924]],
            "left_only": wins, "right_only": losses, "mcnemar_exact_p": pvalue}


def score(out: Path, *, expected_prediction_sha256: str) -> dict:
    verify_files(out, "public.json", "sealed_test_labels.json")
    if file_sha(out / "predictions.json") != expected_prediction_sha256:
        raise RuntimeError("predictions not externally sealed before scoring")
    gold = load(out / "sealed_test_labels.json")
    predictions = load(out / "predictions.json")
    if set(gold) != set(predictions):
        raise ValueError("incomplete prediction set")
    n = len(gold)
    reports = {}
    for name in METHODS:
        correct, accepted, brier = 0, 0, 0.0
        per_seed = {str(seed): {"correct": 0, "n": 0} for seed in SEEDS}
        for k, truth in gold.items():
            pred = predictions[k][name]
            hit = pred["status"] == "ACCEPTED" and pred["prediction"] == truth["test_output"]
            correct += int(hit)
            accepted += int(pred["status"] == "ACCEPTED")
            brier += (float(pred["confidence"]) - int(hit))**2
            group = per_seed[str(truth["seed"])]
            group["correct"] += int(hit)
            group["n"] += 1
        reports[name] = {"correct": correct, "n": n, "raw_accuracy": correct/n, "coverage": accepted/n,
                         "wrong_accepted": accepted-correct, "selective_accuracy": correct/accepted if accepted else None,
                         "wilson_95": wilson(correct, n), "brier_proxy": brier/n,
                         "per_seed": per_seed}
    comparison = paired_effect(predictions, gold, "active_query", "random_query")
    effect = comparison["effect"]
    report = {"protocol": "v3-active-composition-001", "holdout": n,
              "prediction_sha256": file_sha(out / "predictions.json"), "metrics": reports,
              "effect_active_minus_random": effect, "primary_comparison": comparison,
              "secondary_comparisons": {
                  "active_vs_noquery": paired_effect(predictions, gold, "active_query", "no_query"),
                  "macro_ablation": paired_effect(predictions, gold, "active_query", "active_no_macros"),
                  "full_search": paired_effect(predictions, gold, "active_full", "active_query")},
              "gate": {"minimum_effect": 0.05, "passed": effect >= 0.05 and comparison["paired_bootstrap_95"][0] > 0 and all(
                  reports["active_query"]["per_seed"][str(seed)]["correct"] >= reports["random_query"]["per_seed"][str(seed)]["correct"] for seed in SEEDS)},
              "limits": "Synthetic finite program grammar; oracle demonstration IO; no new primitive family, no independent language understanding, no frontier claim"}
    dump(out / "score.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "queries", "feedback", "predict", "score"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--query-sha256", type=str, default="")
    parser.add_argument("--feedback-sha256", type=str, default="")
    parser.add_argument("--prediction-sha256", type=str, default="")
    args = parser.parse_args()
    if args.stage == "prepare": r = prepare(args.out)
    elif args.stage == "queries": r = query_choices(args.out)
    elif args.stage == "feedback": r = release_feedback(args.out, expected_query_sha256=args.query_sha256)
    elif args.stage == "predict": r = predict(args.out, expected_query_sha256=args.query_sha256, expected_feedback_sha256=args.feedback_sha256)
    else: r = score(args.out, expected_prediction_sha256=args.prediction_sha256)
    print(json.dumps(r, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
