#!/usr/bin/env python3
"""Full serialized semantic-jury evaluation for the seven non-symbolic BBH tasks.

Model routing is read from jury_route.json and frozen before execution. Requests
are serialized, Retry-After is honored, every batch is checkpointed, and missing
predictions count as wrong. Gold labels are never included in prompts.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

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
ENDPOINT = "https://models.github.ai/inference/chat/completions"
SYSTEM = (
    "You are the semantic jury inside a proof-carrying reasoning system. "
    "Solve every numbered item carefully. Return ONLY one valid JSON object "
    "mapping each numeric item id string to its exact answer token. Do not reveal "
    "reasoning. Answer every key."
)
DEFAULT_ROUTE = {
    task: {"model": "openai/o3", "mode": semantic.TASK_CONFIG[task][1]}
    for task in TASKS
}


def route_config():
    path = pathlib.Path("jury_route.json")
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_ROUTE, indent=2))
    route = json.loads(path.read_text())
    missing = sorted(set(TASKS) - set(route))
    if missing:
        raise ValueError(f"jury_route.json missing tasks: {missing}")
    return route


def build_prompt(task, mode, items):
    body = ""
    if mode == "cot":
        body += semantic.official_prompt(task) + "\n\n-----\n"
    else:
        body += semantic.task_instruction(task) + "\n\n"
    body += "TEST ITEMS. Return only the JSON answer map.\n\n"
    for item_id, example in items:
        body += f"ITEM {item_id}:\n{example['input']}\n\n"
    return body


def extract_json(content):
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def call(model, task, mode, items, retries=8):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(task, mode, items)},
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
            with urllib.request.urlopen(request, timeout=480) as response:
                raw = response.read().decode(errors="replace")
                headers = dict(response.headers)
            response_data = json.loads(raw)
            message = response_data["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content") or ""
            parsed = extract_json(content)
            answers = {
                semantic.canonical_key(key): semantic.canonical_answer(value)
                for key, value in parsed.items()
            }
            missing = [str(item_id) for item_id, _ in items if str(item_id) not in answers]
            if missing:
                raise ValueError(f"Missing answer ids: {missing}")
            return {"answers": answers, "headers": headers, "message": message}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            last = {
                "type": "HTTPError",
                "status": exc.code,
                "headers": dict(exc.headers),
                "body": body,
            }
            if exc.code not in (429, 500, 502, 503, 504):
                break
            delay = int(exc.headers.get("Retry-After", "30")) + 5
            print("rate/server retry", model, task, exc.code, delay, flush=True)
            time.sleep(delay)
        except Exception as exc:
            last = {"type": type(exc).__name__, "message": str(exc)}
            delay = min(120, 15 * (attempt + 1))
            print("parse/network retry", model, task, repr(exc), delay, flush=True)
            time.sleep(delay)
    raise RuntimeError(json.dumps(last))


def solve_batch(model, task, mode, items):
    try:
        return call(model, task, mode, items)["answers"]
    except Exception as exc:
        if len(items) == 1:
            print("terminal failure", model, task, items[0][0], repr(exc), flush=True)
            return {}
        midpoint = len(items) // 2
        print("split", model, task, len(items), repr(exc), flush=True)
        return {
            **solve_batch(model, task, mode, items[:midpoint]),
            **solve_batch(model, task, mode, items[midpoint:]),
        }


def main():
    route = route_config()
    batch_size = int(os.environ.get("JURY_BATCH", "25"))
    spacing = int(os.environ.get("JURY_SPACING", "35"))
    out = pathlib.Path("artifacts/frontier_jury_full")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": (
            "Frozen route; official public BBH files; no labels in prompts; "
            "serialized requests; exact normalized token scoring; missing answers wrong"
        ),
        "route": route,
        "tasks": {},
    }
    for task in TASKS:
        model = route[task]["model"]
        mode = route[task]["mode"]
        examples = json.loads((semantic.BASE / f"{task}.json").read_text())["examples"]
        cache_path = out / f"{task}__{model.replace('/', '__')}__{mode}.json"
        predictions = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        pending = [(i, ex) for i, ex in enumerate(examples) if str(i) not in predictions]
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            print("batch", task, model, mode, offset, len(batch), flush=True)
            predictions.update(solve_batch(model, task, mode, batch))
            cache_path.write_text(json.dumps(predictions, indent=2, sort_keys=True))
            time.sleep(spacing)
        correct = sum(
            semantic.normalized(predictions.get(str(i), ""))
            == semantic.normalized(example["target"])
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
            if semantic.normalized(predictions.get(str(i), ""))
            != semantic.normalized(example["target"])
        ]
        report["tasks"][task] = {
            "model": model,
            "mode": mode,
            "n": len(examples),
            "correct": correct,
            "accuracy": correct / len(examples),
            "coverage": covered / len(examples),
            "errors": errors[:250],
        }
        (out / "checkpoint_results.json").write_text(json.dumps(report, indent=2))
        print("score", task, correct, len(examples), correct / len(examples), flush=True)
    semantic_sum = sum(value["accuracy"] for value in report["tasks"].values())
    exact_task_points = 19.948
    report["aggregate"] = {
        "semantic_task_count": len(TASKS),
        "semantic_task_point_sum": semantic_sum,
        "semantic_macro_accuracy": semantic_sum / len(TASKS),
        "exact_task_point_sum": exact_task_points,
        "full_bbh_macro_accuracy": (exact_task_points + semantic_sum) / 27,
        "frontier_target": 0.961,
        "beats_target": (exact_task_points + semantic_sum) / 27 > 0.961,
    }
    (out / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
