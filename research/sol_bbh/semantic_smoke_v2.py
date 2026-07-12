#!/usr/bin/env python3
from __future__ import annotations

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
PROMPT_BASE = "https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/cot-prompts"
SYSTEM = """You are a meticulous benchmark reasoning jury. Study the official worked examples, then answer every numbered test item. Return ONLY one valid JSON object mapping each item id string to its exact answer token. Do not reveal reasoning. Preserve the answer token style shown by the item's options. Answer all items."""


def normalized(value):
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def official_prompt(task):
    cache = pathlib.Path(".bbh_prompts") / f"{task}.txt"
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        request = urllib.request.Request(
            f"{PROMPT_BASE}/{task}.txt", headers={"User-Agent": "SOL-BBH/0.2"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            cache.write_bytes(response.read())
    text = cache.read_text()
    return text.split("-----", 1)[-1].strip()


def call(model, task, items):
    body = official_prompt(task)
    body += "\n\n-----\nNow solve these TEST ITEMS. Return only JSON.\n\n"
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
    with urllib.request.urlopen(request, timeout=300) as response:
        data = json.loads(response.read())
    content = data["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    return json.loads(content)


def main():
    models = os.environ.get(
        "MODELS", "openai/gpt-4.1,openai/gpt-4o,deepseek/DeepSeek-R1"
    ).split(",")
    report = {}
    ids = [0, 1, 2, 3, 4, 17, 61, 137, 177, 211]
    for model in models:
        report[model] = {}
        for task in TASKS:
            examples = json.loads((BASE / f"{task}.json").read_text())["examples"]
            items = [(i, examples[i]) for i in ids if i < len(examples)]
            try:
                predictions = call(model, task, items)
                correct = sum(
                    normalized(predictions.get(str(i), "")) == normalized(examples[i]["target"])
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
    pathlib.Path("artifacts/semantic_smoke_v2.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
