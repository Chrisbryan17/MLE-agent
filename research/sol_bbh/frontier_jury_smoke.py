#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

import semantic_full as semantic

MODELS = ("openai/o3", "openai/gpt-5")
TASKS = tuple(semantic.TASK_CONFIG)
SAMPLE_IDS = (0, 1, 2, 3, 4, 17, 61, 137, 177, 211)
ENDPOINT = "https://models.github.ai/inference/chat/completions"
SYSTEM = (
    "You are a meticulous benchmark reasoning jury. Solve every numbered item. "
    "Return ONLY one valid JSON object mapping each numeric item id string to its "
    "exact answer token. Do not reveal reasoning. Answer every key."
)


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


def call(model, task, mode, items, retries=5):
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
            with urllib.request.urlopen(request, timeout=420) as response:
                raw = response.read().decode(errors="replace")
                status = response.status
                headers = dict(response.headers)
            parsed_response = json.loads(raw)
            message = parsed_response["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content") or ""
            answers = extract_json(content)
            answers = {
                semantic.canonical_key(key): semantic.canonical_answer(value)
                for key, value in answers.items()
            }
            missing = [str(item_id) for item_id, _ in items if str(item_id) not in answers]
            if missing:
                raise ValueError(f"Missing answer ids: {missing}")
            return {
                "ok": True,
                "status": status,
                "headers": headers,
                "message": message,
                "answers": answers,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            last = {
                "type": "HTTPError",
                "status": exc.code,
                "reason": str(exc.reason),
                "headers": dict(exc.headers),
                "body": body,
            }
            if exc.code not in (429, 500, 502, 503, 504):
                break
            retry_after = int(exc.headers.get("Retry-After", "30"))
            time.sleep(retry_after + 5)
        except Exception as exc:
            last = {"type": type(exc).__name__, "message": str(exc)}
            time.sleep(20 * (attempt + 1))
    return {"ok": False, "error": last}


def main():
    out = pathlib.Path("artifacts/frontier_jury_smoke")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "Serialized frontier-jury smoke; deterministic sample; no gold labels in prompts",
        "models": MODELS,
        "sample_ids": SAMPLE_IDS,
        "results": {},
    }
    for model in MODELS:
        report["results"][model] = {}
        for task in TASKS:
            examples = json.loads((semantic.BASE / f"{task}.json").read_text())["examples"]
            items = [(i, examples[i]) for i in SAMPLE_IDS if i < len(examples)]
            _, mode = semantic.TASK_CONFIG[task]
            result = call(model, task, mode, items)
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
            report["results"][model][task] = result
            print(model, task, result.get("score", {}).get("accuracy"), result.get("error"), flush=True)
            (out / "checkpoint.json").write_text(json.dumps(report, indent=2))
            time.sleep(35)
        scored = [
            value["score"]["accuracy"]
            for value in report["results"][model].values()
            if value.get("ok") and "score" in value
        ]
        report["results"][model]["aggregate"] = {
            "tasks_scored": len(scored),
            "macro_accuracy": sum(scored) / len(scored) if scored else 0.0,
        }
    (out / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({
        model: report["results"][model]["aggregate"] for model in MODELS
    }, indent=2))


if __name__ == "__main__":
    main()
