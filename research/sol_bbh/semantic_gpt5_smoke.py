#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib

import semantic_full as jury

TASKS = list(jury.TASK_CONFIG)
IDS = [0, 1, 2, 3, 4, 17, 61, 137, 177, 211, 223, 241]


def main():
    output = pathlib.Path("artifacts/gpt5_smoke.json")
    report = {}
    for task in TASKS:
        examples = json.loads((jury.BASE / f"{task}.json").read_text())["examples"]
        items = [(i, examples[i]) for i in IDS if i < len(examples)]
        # Use the frozen task prompt mode, but replace the model with GPT-5.
        _, mode = jury.TASK_CONFIG[task]
        predictions = jury.solve_batch("openai/gpt-5", task, mode, items)
        correct = sum(
            jury.normalized(predictions.get(str(i), "")) == jury.normalized(examples[i]["target"])
            for i, _ in items
        )
        report[task] = {
            "model": "openai/gpt-5",
            "mode": mode,
            "correct": correct,
            "n": len(items),
            "accuracy": correct / len(items),
            "predictions": predictions,
            "gold": {str(i): examples[i]["target"] for i, _ in items},
        }
        print(task, correct, len(items), correct / len(items), flush=True)
    report["aggregate"] = {
        "macro_accuracy": sum(value["accuracy"] for key, value in report.items() if key != "aggregate") / len(TASKS)
    }
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
