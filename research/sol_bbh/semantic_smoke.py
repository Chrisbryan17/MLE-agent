#!/usr/bin/env python3
import json
import os
import pathlib
import re
import time
import urllib.request

TASKS = [
    "causal_judgement",
    "disambiguation_qa",
    "formal_fallacies",
    "movie_recommendation",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
]
BASE = pathlib.Path(".bbh_cache")
ENDPOINT = "https://models.github.ai/inference/chat/completions"
SYSTEM = """You are a meticulous benchmark reasoning jury. Answer every numbered item. Return ONLY a JSON object mapping each item id string to its exact answer token. Do not include explanations. Use the options exactly: for example, \"(A)\", \"Yes\", \"no\", or \"valid\". Reason privately before answering."""


def call(model, task, items):
    body = "TASK: " + task + "\n\n"
    for item_id, example in items:
        body += f"ITEM {item_id}:\n{example['input']}\n\n"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": body},
        ],
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.loads(response.read())
    content = data["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    return json.loads(content)


def main():
    models = os.environ.get("MODELS", "openai/gpt-4.1,openai/gpt-4o").split(",")
    report = {}
    for model in models:
        report[model] = {}
        for task in TASKS:
            examples = json.loads((BASE / f"{task}.json").read_text())["examples"]
            ids = [0, 1, 2, 3, 4, 17, 61, 137]
            items = [(i, examples[i]) for i in ids if i < len(examples)]
            try:
                predictions = call(model, task, items)
                correct = sum(
                    str(predictions.get(str(i), "")).strip() == examples[i]["target"].strip()
                    for i, _ in items
                )
                report[model][task] = {
                    "accuracy": correct / len(items),
                    "correct": correct,
                    "n": len(items),
                    "predictions": predictions,
                    "gold": {str(i): examples[i]["target"] for i, _ in items},
                }
            except Exception as exc:
                report[model][task] = {"error": f"{type(exc).__name__}: {exc}"}
            print(model, task, report[model][task].get("accuracy"), report[model][task].get("error"))
            time.sleep(1)
    pathlib.Path("artifacts/semantic_smoke.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
