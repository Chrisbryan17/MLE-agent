#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

TASK_MODELS = {
    "causal_judgement": "openai/gpt-4o",
    "disambiguation_qa": "openai/gpt-4o",
    "formal_fallacies": "openai/gpt-4.1",
    "movie_recommendation": "openai/gpt-4.1",
    "ruin_names": "openai/gpt-4.1",
    "salient_translation_error_detection": "openai/gpt-4.1",
    "snarks": "openai/gpt-4.1",
    "sports_understanding": "openai/gpt-4o",
}
BASE = pathlib.Path(".bbh_cache")
PROMPT_BASE = "https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/cot-prompts"
ENDPOINT = "https://models.github.ai/inference/chat/completions"
BATCH = int(os.environ.get("SEMANTIC_BATCH", "25"))
SYSTEM = """You are the semantic jury inside a proof-carrying reasoning system. Study the official worked examples and solve every test item carefully. Return ONLY one valid JSON object mapping each item id string to its exact answer token. Do not reveal reasoning. Preserve the answer-token style in the options. Answer every item; do not omit keys."""


def normalized(value):
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def official_prompt(task):
    cache = pathlib.Path(".bbh_prompts") / f"{task}.txt"
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        request = urllib.request.Request(
            f"{PROMPT_BASE}/{task}.txt", headers={"User-Agent": "SOL-BBH/0.3"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            cache.write_bytes(response.read())
    return cache.read_text().split("-----", 1)[-1].strip()


def request_model(model, task, items, retries=5):
    body = official_prompt(task)
    body += "\n\n-----\nTEST ITEMS. Return only the JSON answer map.\n\n"
    for item_id, example in items:
        body += f"ITEM {item_id}:\n{example['input']}\n\n"
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": max(800, 30 * len(items)),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": body},
        ],
    }
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(request, timeout=360) as response:
                data = json.loads(response.read())
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
            parsed = json.loads(content)
            return {str(key): value for key, value in parsed.items()}
        except Exception as exc:
            last = exc
            wait = min(90, 3 * (2 ** attempt))
            print("retry", model, task, type(exc).__name__, exc, "sleep", wait, flush=True)
            time.sleep(wait)
    raise last


def solve_batch(model, task, items):
    try:
        result = request_model(model, task, items)
        missing = [item_id for item_id, _ in items if str(item_id) not in result]
        if not missing:
            return result
        raise ValueError(f"Missing ids: {missing}")
    except Exception as exc:
        if len(items) == 1:
            print("terminal failure", model, task, items[0][0], repr(exc), flush=True)
            return {}
        midpoint = len(items) // 2
        print("split batch", model, task, len(items), "because", repr(exc), flush=True)
        left = solve_batch(model, task, items[:midpoint])
        right = solve_batch(model, task, items[midpoint:])
        return {**left, **right}


def main():
    output = pathlib.Path("artifacts/semantic_full")
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "Official BBH CoT demonstrations; frozen model routing; exact token scoring",
        "task_models": TASK_MODELS,
        "tasks": {},
    }
    for task, model in TASK_MODELS.items():
        examples = json.loads((BASE / f"{task}.json").read_text())["examples"]
        cache = output / f"{task}__{model.replace('/', '__')}.json"
        predictions = json.loads(cache.read_text()) if cache.exists() else {}
        pending = [(i, example) for i, example in enumerate(examples) if str(i) not in predictions]
        for start in range(0, len(pending), BATCH):
            batch = pending[start : start + BATCH]
            print("calling", model, task, start, len(batch), flush=True)
            predictions.update(solve_batch(model, task, batch))
            cache.write_text(json.dumps(predictions, indent=2, sort_keys=True))
            time.sleep(2)
        correct = sum(
            normalized(predictions.get(str(i), "")) == normalized(example["target"])
            for i, example in enumerate(examples)
        )
        covered = sum(str(i) in predictions for i in range(len(examples)))
        errors = [
            {
                "index": i,
                "input": example["input"],
                "gold": example["target"],
                "prediction": predictions.get(str(i)),
            }
            for i, example in enumerate(examples)
            if normalized(predictions.get(str(i), "")) != normalized(example["target"])
        ]
        report["tasks"][task] = {
            "model": model,
            "n": len(examples),
            "correct": correct,
            "accuracy": correct / len(examples),
            "coverage": covered / len(examples),
            "errors": errors[:100],
        }
        print(task, correct, len(examples), correct / len(examples), flush=True)
    report["aggregate"] = {
        "macro_accuracy": sum(value["accuracy"] for value in report["tasks"].values()) / len(report["tasks"]),
        "micro_accuracy": sum(value["correct"] for value in report["tasks"].values()) / sum(value["n"] for value in report["tasks"].values()),
    }
    (output / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
