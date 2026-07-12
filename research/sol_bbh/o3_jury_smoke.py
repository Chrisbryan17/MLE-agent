#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import time

import frontier_jury_smoke as jury
import semantic_full as semantic

TASKS = (
    "causal_judgement",
    "disambiguation_qa",
    "movie_recommendation",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
)
SAMPLE_IDS = (0, 1, 2, 3, 4, 9, 17, 29, 41, 61, 79, 97, 113, 137, 151, 177, 191, 211, 223, 241)
MODEL = "openai/o3"


def main():
    out = pathlib.Path("artifacts/o3_jury_smoke")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "o3-only serialized confirmation; deterministic 20-item sample; no labels in prompts",
        "model": MODEL,
        "sample_ids": SAMPLE_IDS,
        "tasks": {},
    }
    for task in TASKS:
        examples = json.loads((semantic.BASE / f"{task}.json").read_text())["examples"]
        items = [(i, examples[i]) for i in SAMPLE_IDS if i < len(examples)]
        _, mode = semantic.TASK_CONFIG[task]
        result = jury.call(MODEL, task, mode, items, retries=7)
        if result.get("ok"):
            answers = result["answers"]
            correct = sum(
                semantic.normalized(answers.get(str(i), ""))
                == semantic.normalized(examples[i]["target"])
                for i, _ in items
            )
            result["score"] = {
                "correct": correct,
                "n": len(items),
                "accuracy": correct / len(items),
                "gold": {str(i): examples[i]["target"] for i, _ in items},
            }
        report["tasks"][task] = result
        (out / "checkpoint.json").write_text(json.dumps(report, indent=2))
        print(task, result.get("score", {}).get("accuracy"), result.get("error"), flush=True)
        time.sleep(35)
    scores = [value["score"]["accuracy"] for value in report["tasks"].values() if value.get("ok")]
    report["aggregate"] = {
        "tasks_scored": len(scores),
        "macro_accuracy": sum(scores) / len(scores) if scores else 0.0,
        "required_semantic_macro": 5.999 / 7,
        "projected_full_bbh_macro": (19.948 + sum(scores)) / 27 if len(scores) == 7 else None,
    }
    (out / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
