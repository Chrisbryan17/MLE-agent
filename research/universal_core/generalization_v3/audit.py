"""Read-only independent arithmetic/integrity audit of revealed Pilot 002.

Does not write to, repair, or change any frozen predictions or score file.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from experiment import SEEDS, METHODS, BUDGET, file_sha, generate


def audit(out: Path) -> dict:
    read = lambda name: json.loads((out / name).read_text(encoding="utf-8"))
    committed = read("commitments.json")
    for name, digest in committed["sha256"].items():
        if file_sha(out / name) != digest:
            raise AssertionError(f"commitment digest mismatch {name}")
    actual_public, actual_gold, actual_oracle = generate()
    if read("public.json") != actual_public or read("sealed_test_labels.json") != actual_gold or read("sealed_query_oracle.json") != actual_oracle:
        raise AssertionError("generated data failed deterministic replication")
    public = read("public.json")
    predictions, gold, queries, feedback, oracle = (read(x) for x in ("predictions.json", "sealed_test_labels.json", "queries.json", "feedback.json", "sealed_query_oracle.json"))
    score = read("score.json")
    assert len(public["train"]) == 108 and len(public["holdout"]) == len(gold) == 180
    assert set(predictions) == set(gold) == set(queries) == set(feedback)
    for k, selections in queries.items():
        for method, idx in selections.items():
            assert feedback[k][method] == oracle[k][idx], f"query feedback mismatch: {k} {method}"
    per_method = {}
    for name in METHODS:
        hits = {seed: [] for seed in SEEDS}
        stats = Counter()
        for taskid in sorted(gold):
            truth = gold[taskid]
            p = predictions[taskid][name]
            correct = p["status"] == "ACCEPTED" and p["prediction"] == truth["test_output"]
            stats["correct"] += int(correct)
            stats["accepted"] += int(p["status"] == "ACCEPTED")
            hits[truth["seed"]].append(int(correct))
        expected = score["metrics"][name]
        assert stats["correct"] == expected["correct"]
        assert stats["accepted"] - stats["correct"] == expected["wrong_accepted"]
        assert abs(stats["correct"]/180-expected["raw_accuracy"]) < 1e-12
        for seed in SEEDS:
            assert sum(hits[seed]) == expected["per_seed"][str(seed)]["correct"]
            assert len(hits[seed]) == 60
        per_method[name] = {"correct": stats["correct"], "accepted": stats["accepted"],
                            "per_seed": {str(seed): sum(hits[seed]) for seed in SEEDS}}
    a = per_method["active_query"]["correct"]
    b = per_method["random_query"]["correct"]
    assert abs((a-b)/180-score["primary_comparison"]["effect"]) < 1e-12
    assert not score["gate"]["passed"]
    return {"verified": True, "cases": 180, "seed_streams": list(SEEDS),
            "commitments_sha256": file_sha(out / "commitments.json"),
            "prediction_sha256": file_sha(out / "predictions.json"),
            "score_sha256": file_sha(out / "score.json"),
            "query_sha256": file_sha(out / "queries.json"),
            "feedback_sha256": file_sha(out / "feedback.json"),
            "method_totals": per_method, "primary_gate_passed": False,
            "audit_status": "read_only_post_reveal_no_parameter_changes"}


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evidence/pilot-002")
    print(json.dumps(audit(path), sort_keys=True, indent=2))
