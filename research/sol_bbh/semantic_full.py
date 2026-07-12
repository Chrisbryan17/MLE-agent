#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.request

TASK_CONFIG = {
    "causal_judgement": ("openai/gpt-4o", "cot"),
    "disambiguation_qa": ("openai/gpt-4o", "cot"),
    "formal_fallacies": ("openai/gpt-4.1", "zero"),
    "movie_recommendation": ("openai/gpt-4.1", "zero"),
    "ruin_names": ("openai/gpt-4.1", "zero"),
    "salient_translation_error_detection": ("openai/gpt-4.1", "zero"),
    "snarks": ("openai/gpt-4.1", "zero"),
    "sports_understanding": ("openai/gpt-4o", "zero"),
}
BASE = pathlib.Path(".bbh_cache")
PROMPT_BASE = "https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/cot-prompts"
ENDPOINT = "https://models.github.ai/inference/chat/completions"
BATCH = int(os.environ.get("SEMANTIC_BATCH", "25"))
SYSTEM = """You are the semantic jury inside a proof-carrying reasoning system. Solve every numbered item carefully. Return ONLY one valid JSON object mapping each numeric item id string to its exact answer token. Do not reveal reasoning. Answer every item; do not omit keys."""


def canonical_key(value):
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else str(value).strip()


def canonical_answer(value):
    text = re.sub(r"\s+", " ", str(value).strip())
    if re.fullmatch(r"[A-Z]", text, re.I):
        return f"({text.upper()})"
    match = re.fullmatch(r"\(?([A-Z])\)?[.)]?", text, re.I)
    if match:
        return f"({match.group(1).upper()})"
    return text


def normalized(value):
    return canonical_answer(value).lower()


def official_prompt(task):
    cache = pathlib.Path(".bbh_prompts") / f"{task}.txt"
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        request = urllib.request.Request(
            f"{PROMPT_BASE}/{task}.txt", headers={"User-Agent": "SOL-BBH/0.4"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            cache.write_bytes(response.read())
    return cache.read_text().split("-----", 1)[-1].strip()


def task_instruction(task):
    return {
        "formal_fallacies": "Determine whether each conclusion follows deductively from only the stated premises. Do not affirm the consequent or reverse implications.",
        "movie_recommendation": "Choose the option most similar in broad popularity, genre, tone, era, or audience to the listed movies.",
        "ruin_names": "Choose the intentionally humorous one-character or tiny edit that forms a recognizable pun, not a random typo.",
        "salient_translation_error_detection": "Compare source and translation and classify the single most salient error using the categories stated in each item.",
        "snarks": "Choose the sarcastic statement: the one whose literal wording clashes with context, commonsense, or the speaker's implied attitude.",
        "sports_understanding": "Judge whether the named athlete and described action form a plausible real-sport statement; check both the athlete's sport and whether the action belongs to it.",
    }.get(task, "Solve according to ordinary language and the options.")


def request_model(model, task, mode, items, retries=7):
    body = ""
    if mode == "cot":
        body += official_prompt(task) + "\n\n-----\n"
    else:
        body += task_instruction(task) + "\n\n"
    body += "TEST ITEMS. Return only the JSON answer map.\n\n"
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
            return {
                canonical_key(key): canonical_answer(value)
                for key, value in parsed.items()
            }
        except Exception as exc:
            last = exc
            wait = min(120, 8 * (attempt + 1))
            print("retry", model, task, type(exc).__name__, exc, "sleep", wait, flush=True)
            time.sleep(wait)
    raise last


def solve_batch(model, task, mode, items):
    try:
        result = request_model(model, task, mode, items)
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
        left = solve_batch(model, task, mode, items[:midpoint])
        right = solve_batch(model, task, mode, items[midpoint:])
        return {**left, **right}


def main():
    output = pathlib.Path("artifacts/semantic_full")
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "Frozen mixed prompt routing; official CoT only where selected; exact normalized token scoring",
        "task_config": TASK_CONFIG,
        "tasks": {},
    }
    for task, (model, mode) in TASK_CONFIG.items():
        examples = json.loads((BASE / f"{task}.json").read_text())["examples"]
        cache = output / f"{task}__{model.replace('/', '__')}__{mode}.json"
        predictions = json.loads(cache.read_text()) if cache.exists() else {}
        pending = [(i, example) for i, example in enumerate(examples) if str(i) not in predictions]
        for start in range(0, len(pending), BATCH):
            batch = pending[start : start + BATCH]
            print("calling", model, mode, task, start, len(batch), flush=True)
            predictions.update(solve_batch(model, task, mode, batch))
            cache.write_text(json.dumps(predictions, indent=2, sort_keys=True))
            time.sleep(8)
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
            "mode": mode,
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
