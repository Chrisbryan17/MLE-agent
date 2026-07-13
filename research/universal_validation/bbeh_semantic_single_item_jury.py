#!/usr/bin/env python3
"""Prediction-sealed single-item jury for the seven residual semantic BBEH tasks.

The previous batched jury mixed many benchmark items into one prompt. That was
especially destructive for Linguini, whose own inputs contain numbered blanks
that collided with batch JSON ids. This runner sends exactly one redacted input
per request, extracts one tagged final answer, seals predictions, and only then
loads targets in a separate scoring phase.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = "https://models.github.ai/inference/chat/completions"
ROOT = pathlib.Path(os.environ.get("BBEH_TASK_ROOT", ".external/bbeh/bbeh/benchmark_tasks"))

TASK_GUIDANCE = {
    "bbeh_disambiguation_qa": (
        "Resolve every pronoun antecedent using syntax, grammatical roles, discourse continuity, "
        "selectional constraints, and commonsense. Compare your interpretation to all options. "
        "Return exactly one option label such as (A), (B), (C), (D), or (E)."
    ),
    "bbeh_movie_recommendation": (
        "Each option is a SET of five movies. Select the option whose five movies are most mutually "
        "similar in whether the same audience would like them, considering genre, tone, era, quality, "
        "themes, and mass-versus-art-house appeal. Do not choose one movie. Return exactly one option "
        "label such as (A)."
    ),
    "bbeh_sarc_triples": (
        "Classify each of the three Reddit replies independently as sarcastic (1) or not sarcastic (0). "
        "Sarcasm normally requires an intended meaning that conflicts with the literal wording or an "
        "obviously exaggerated/ironic stance. Return exactly three comma-separated bits, for example 1,0,0."
    ),
    "bbeh_sportqa": (
        "Answer the main sports-rules question and the two subquestions independently. For each, select "
        "all correct option letters under the stated league rules. Return exactly three comma-separated "
        "answer groups in the benchmark format, for example A, C, A or AB, D, AC."
    ),
    "bbeh_causal_understanding": (
        "Apply ordinary human actual-causation judgment. Distinguish abnormal interventions and policy "
        "violations from normal background conditions, but follow the majority-human standard stated in "
        "the item. Return exactly Yes, No, or Ambiguous."
    ),
    "bbeh_nycc": (
        "Choose the funniest New Yorker caption. Prefer concise, scene-specific incongruity, a clean "
        "conceptual twist, and social observation over generic puns or merely descriptive text. Return "
        "exactly one option label such as (A)."
    ),
    "bbeh_linguini": (
        "Solve this linguistics-olympiad induction problem from the demonstrations inside this ONE item. "
        "Infer the relevant morphology, phonology, syntax, agreement, or writing-system rule. The item may "
        "contain numbered blanks; those numbers are internal to the puzzle and are not response ids. Return "
        "only the exact requested missing form, preserving articles, brackets, spaces, punctuation, accents, "
        "IPA symbols, capitalization, and diacritics."
    ),
}

SYSTEM = (
    "You are solving one benchmark item. Reason carefully in private. Your visible response must contain "
    "exactly one final-answer tag and nothing else: <FINAL>answer</FINAL>. Never emit JSON, item ids, an "
    "explanation, or answers to any other numbered blanks in the input."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def extract_answer(message: dict[str, Any]) -> str:
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""
    combined = content if content.strip() else reasoning
    matches = re.findall(r"<FINAL>\s*(.*?)\s*</FINAL>", combined, re.I | re.S)
    if matches:
        return canonical(matches[-1])
    # Conservative fallback for models that obey the no-explanation constraint but omit tags.
    cleaned = re.sub(r"^```(?:text)?\s*|\s*```$", "", combined.strip(), flags=re.I | re.S)
    lines = [x.strip() for x in cleaned.splitlines() if x.strip()]
    if len(lines) == 1:
        return canonical(lines[0])
    m = re.search(r"(?:final answer|answer)\s*[:=-]\s*(.+)$", cleaned, re.I | re.M)
    if m:
        return canonical(m.group(1))
    raise ValueError("No uniquely extractable final answer")


def request(model: str, task: str, text: str, retries: int = 10) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": TASK_GUIDANCE[task] + "\n\nBENCHMARK ITEM:\n" + text},
        ],
        "temperature": 0,
    }
    last: dict[str, Any] | None = None
    for attempt in range(retries):
        started = time.time()
        try:
            req = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                    "Content-Type": "application/json",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with urllib.request.urlopen(req, timeout=1200) as response:
                decoded = json.loads(response.read().decode(errors="replace"))
                headers = dict(response.headers)
            message = decoded["choices"][0]["message"]
            answer = extract_answer(message)
            return {
                "ok": True,
                "answer": answer,
                "message": message,
                "usage": decoded.get("usage"),
                "headers": headers,
                "latency_seconds": time.time() - started,
            }
        except urllib.error.HTTPError as exc:
            last = {
                "type": "HTTPError",
                "status": exc.code,
                "headers": dict(exc.headers),
                "body": exc.read().decode(errors="replace"),
            }
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break
            time.sleep(int(exc.headers.get("Retry-After", "30")) + 5)
        except Exception as exc:
            last = {"type": type(exc).__name__, "message": str(exc)}
            time.sleep(min(120, 8 * (attempt + 1)))
    return {"ok": False, "error": last}


def original_path(task: str) -> pathlib.Path:
    return ROOT / task / "task.json"


def redact(task: str, out: pathlib.Path) -> dict[str, Any]:
    source = original_path(task)
    examples = json.loads(source.read_text())["examples"]
    payload = {
        "task": task,
        "pinned_bbeh_commit": "80d12ca916b7158f22293fcf3144f4d3d854d4be",
        "source_task_sha256": sha256_bytes(source.read_bytes()),
        "items": [
            {"index": i, "input": example["input"], "input_sha256": sha256_bytes(example["input"].encode())}
            for i, example in enumerate(examples)
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / "REDACTED_INPUTS.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return payload


def predict(task: str, model: str, out: pathlib.Path) -> dict[str, Any]:
    redacted_path = out / "REDACTED_INPUTS.json"
    redacted = json.loads(redacted_path.read_text())
    if redacted["task"] != task:
        raise ValueError("task mismatch")
    checkpoint_path = out / "PREDICTION_CHECKPOINT.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {
        "task": task,
        "model": model,
        "redacted_inputs_sha256": sha256_bytes(redacted_path.read_bytes()),
        "predictions": {},
        "raw": {},
    }
    for item in redacted["items"]:
        key = str(item["index"])
        if key in checkpoint["predictions"]:
            continue
        result = request(model, task, item["input"])
        checkpoint["raw"][key] = result
        checkpoint["predictions"][key] = result.get("answer") if result.get("ok") else None
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False, default=str) + "\n")
        if (item["index"] + 1) % 10 == 0:
            print(task, item["index"] + 1, "/", len(redacted["items"]), flush=True)
        time.sleep(0.15)
    core = {
        "task": task,
        "model": model,
        "redacted_inputs_sha256": checkpoint["redacted_inputs_sha256"],
        "predictions": checkpoint["predictions"],
        "raw": checkpoint["raw"],
        "protocol": "single redacted input per request; targets unavailable during prediction",
    }
    core["prediction_map_sha256"] = sha256_bytes(
        json.dumps(core["predictions"], sort_keys=True, ensure_ascii=False).encode()
    )
    path = out / "PREDICTIONS.json"
    path.write_text(json.dumps(core, indent=2, ensure_ascii=False, default=str) + "\n")
    seal = {
        "REDACTED_INPUTS.json": sha256_bytes(redacted_path.read_bytes()),
        "PREDICTIONS.json": sha256_bytes(path.read_bytes()),
    }
    seal_path = out / "PREDICTION_SEAL.json"
    seal_path.write_text(json.dumps(seal, indent=2) + "\n")
    return {"prediction_seal_sha256": sha256_bytes(seal_path.read_bytes()), "n": len(core["predictions"])}


def normalize(task: str, value: Any) -> str:
    text = canonical(value or "")
    if task in {"bbeh_disambiguation_qa", "bbeh_movie_recommendation", "bbeh_nycc"}:
        m = re.search(r"[A-J]", text.upper())
        return f"({m.group(0)})" if m else text
    if task == "bbeh_causal_understanding":
        return text.title()
    if task in {"bbeh_sarc_triples", "bbeh_sportqa"}:
        return re.sub(r"\s*,\s*", ",", text.upper() if task == "bbeh_sportqa" else text)
    return text


def score(task: str, out: pathlib.Path) -> dict[str, Any]:
    seal_path = out / "PREDICTION_SEAL.json"
    seal = json.loads(seal_path.read_text())
    for name, digest in seal.items():
        path = out / name
        if sha256_bytes(path.read_bytes()) != digest:
            raise RuntimeError("seal mismatch: " + name)
    redacted = json.loads((out / "REDACTED_INPUTS.json").read_text())
    predictions = json.loads((out / "PREDICTIONS.json").read_text())
    source = original_path(task)
    if sha256_bytes(source.read_bytes()) != redacted["source_task_sha256"]:
        raise RuntimeError("task file changed")
    examples = json.loads(source.read_text())["examples"]
    rows = []
    for i, example in enumerate(examples):
        if sha256_bytes(example["input"].encode()) != redacted["items"][i]["input_sha256"]:
            raise RuntimeError(f"input mismatch at {i}")
        prediction = predictions["predictions"].get(str(i))
        p = normalize(task, prediction)
        target = normalize(task, example["target"])
        rows.append({"index": i, "prediction": prediction, "normalized_prediction": p, "target": example["target"], "correct": p == target})
    correct = sum(row["correct"] for row in rows)
    result = {
        "task": task,
        "model": predictions["model"],
        "evidence_class": "blind/frozen model-assisted predictions sealed before scoring on the pinned public set",
        "correct": correct,
        "total": len(rows),
        "accuracy": correct / len(rows),
        "coverage": sum(predictions["predictions"].get(str(i)) is not None for i in range(len(rows))) / len(rows),
        "prediction_seal_sha256": sha256_bytes(seal_path.read_bytes()),
        "errors": [row for row in rows if not row["correct"]],
    }
    (out / "SCORED_RESULTS.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("redact", "predict", "score"), required=True)
    ap.add_argument("--task", choices=sorted(TASK_GUIDANCE), required=True)
    ap.add_argument("--model")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()
    if args.phase == "redact":
        value = redact(args.task, args.out)
        print(json.dumps({"task": args.task, "n": len(value["items"]), "source_task_sha256": value["source_task_sha256"]}, indent=2))
    elif args.phase == "predict":
        if not args.model:
            raise SystemExit("--model is required for prediction")
        print(json.dumps(predict(args.task, args.model, args.out), indent=2))
    else:
        result = score(args.task, args.out)
        print(json.dumps({k: v for k, v in result.items() if k != "errors"}, indent=2))


if __name__ == "__main__":
    main()
