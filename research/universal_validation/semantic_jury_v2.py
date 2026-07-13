#!/usr/bin/env python3
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
from typing import Any, Iterable

ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_TASK_ROOT = pathlib.Path(".external/bbeh/bbeh/benchmark_tasks")
TASKS = (
    "bbeh_causal_understanding", "bbeh_disambiguation_qa", "bbeh_linguini",
    "bbeh_movie_recommendation", "bbeh_nycc", "bbeh_sarc_triples", "bbeh_sportqa",
)
MODELS = ("openai/gpt-4o-mini", "cohere/Cohere-command-a")
INSTRUCTIONS = {
    "bbeh_causal_understanding": "Answer ordinary-language actual-causation judgments. Apply counterfactual dependence, causal structure, normality and norm violations, omissions and responsibilities. Distinguish an abnormal intervention from a normal background condition. Return exactly Yes, No, or Ambiguous for each item.",
    "bbeh_disambiguation_qa": "Resolve every pronoun and reference compositionally. Track grammatical subject/object roles, quotation and reported-speech scope, semantic plausibility, and discourse continuity. Compare the resulting complete antecedent assignment against the listed options. Return exactly one option marker such as (A).",
    "bbeh_linguini": "Infer the hidden linguistic system from all demonstrations in the item. Solve morphology, phonology, syntax, agreement, case, number, word order, and arithmetic/code mappings when present. Verify the inferred rule against every available row, then return only the exact requested missing form or translation.",
    "bbeh_movie_recommendation": "Choose the option whose five films are most internally homogeneous in audience preference. Use genre, era, tone, mainstream/art-house status, demographic appeal, and likely collaborative-filtering co-likes. Return exactly one option marker such as (A).",
    "bbeh_nycc": "Choose the funniest New Yorker-caption option. Prefer scene-specific visual incongruity, compressed wit, a clean surprise, and socially observant subtext; penalize generic jokes, explanation, and captions that do not exploit the depicted scene. Return exactly one option marker such as (A).",
    "bbeh_sarc_triples": "Classify each of the three Reddit replies independently as sarcastic (1) or literal/non-sarcastic (0). Look for polarity reversal, praise used as criticism, absurd literalization, rhetorical understatement, and context conflict. Return exactly three comma-separated bits, for example 1,0,0.",
    "bbeh_sportqa": "Solve the main sports-rules question and both subquestions. For each question select every correct listed choice, preserving the benchmark's exact compact format. Apply the named sport's official rules, event chronology, scoring, possession, fouls, boundaries, and physical constraints. Return exactly three comma-separated answer groups.",
}
SYSTEM = "You are a meticulous benchmark solver. Solve every numbered item independently. Before answering, silently verify the result against the question and required output grammar. Return only one valid JSON object mapping every numeric item id string to its exact final answer. No explanations, markdown, or omitted keys."

def canonical(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S | re.I).strip()
    return re.sub(r"\s+", " ", text)

def normalized(value: Any) -> str:
    text = canonical(value).lower().replace(" ,", ",")
    return f"({text})" if re.fullmatch(r"[a-z]", text) else text

def extract_json(content: str) -> dict[str, str]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.S | re.I).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match: raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict): raise TypeError("Expected JSON object")
    result = {}
    for key, answer in value.items():
        match = re.search(r"\d+", str(key))
        if match: result[match.group(0)] = canonical(answer)
    return result

def batches(examples: list[dict[str, Any]], max_items: int = 12, max_chars: int = 45000) -> Iterable[list[tuple[int, dict[str, Any]]]]:
    current, chars = [], 0
    for index, example in enumerate(examples):
        size = len(example["input"])
        if current and (len(current) >= max_items or chars + size > max_chars):
            yield current
            current, chars = [], 0
        current.append((index, example)); chars += size
    if current: yield current

def build_prompt(task: str, items: list[tuple[int, dict[str, Any]]]) -> str:
    blocks = [INSTRUCTIONS[task], "", "TEST ITEMS:", ""]
    for index, example in items: blocks.extend((f"ITEM {index}:", example["input"], ""))
    blocks.append("Return only the complete JSON answer map.")
    return "\n".join(blocks)

def request(model: str, task: str, items: list[tuple[int, dict[str, Any]]], retries: int = 6) -> dict[str, Any]:
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build_prompt(task, items)}], "temperature": 0}
    last = None
    for attempt in range(retries):
        started = time.time()
        try:
            req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Content-Type": "application/json", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
            with urllib.request.urlopen(req, timeout=1200) as response:
                raw, headers, status = response.read().decode(errors="replace"), dict(response.headers), response.status
            decoded = json.loads(raw); message = decoded["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content") or ""
            answers = extract_json(content)
            missing = [str(index) for index, _ in items if str(index) not in answers]
            if missing: raise ValueError(f"missing ids {missing}")
            return {"ok": True, "answers": answers, "status": status, "headers": headers, "usage": decoded.get("usage"), "latency_seconds": time.time() - started, "raw_message": message}
        except urllib.error.HTTPError as exc:
            last = {"type": "HTTPError", "status": exc.code, "headers": dict(exc.headers), "body": exc.read().decode(errors="replace")[:4000]}
            if exc.code not in (408, 429, 500, 502, 503, 504): break
            time.sleep(min(int(exc.headers.get("Retry-After", "20")) + 2, 90))
        except Exception as exc:
            last = {"type": type(exc).__name__, "message": str(exc)}
            time.sleep(min(60, 5 * (attempt + 1)))
    return {"ok": False, "error": last}

def safe_model(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")

def predict(task: str, model: str, task_root: pathlib.Path, out: pathlib.Path) -> None:
    path = task_root / task / "task.json"; examples = json.loads(path.read_text())["examples"]; out.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {"task": task, "model": model, "predictions": {}, "raw_batches": []}
    predictions = checkpoint["predictions"]
    for batch in batches(examples):
        pending = [item for item in batch if str(item[0]) not in predictions]
        if not pending: continue
        queue = [pending]
        while queue:
            subset = queue.pop(0); result = request(model, task, subset)
            checkpoint["raw_batches"].append({"ids": [i for i, _ in subset], "result": result})
            if result.get("ok"): predictions.update(result["answers"])
            elif len(subset) > 1:
                middle = len(subset) // 2; queue.extend((subset[:middle], subset[middle:]))
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, default=str) + "\n")
        print(task, model, len(predictions), "/", len(examples), flush=True)
    ordered = {str(i): predictions.get(str(i)) for i in range(len(examples))}
    seal = {"protocol": "Predictions generated from task inputs only and sealed before any scoring job receives labels.", "task": task, "model": model, "task_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "code_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), "prediction_sha256": hashlib.sha256(json.dumps(ordered, sort_keys=True).encode()).hexdigest(), "n": len(examples), "coverage": sum(v is not None for v in ordered.values()) / len(examples), "predictions": ordered, "raw_batches": checkpoint["raw_batches"]}
    (out / f"{task}__{safe_model(model)}.predictions.json").write_text(json.dumps(seal, indent=2, default=str) + "\n")
    (out / "SEAL.sha256").write_text(hashlib.sha256(json.dumps(seal, sort_keys=True, default=str).encode()).hexdigest() + "\n")

def score(task_root: pathlib.Path, prediction_root: pathlib.Path, out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True); sealed = {}
    for path in sorted(prediction_root.rglob("*.predictions.json")):
        payload = json.loads(path.read_text()); sealed[(payload["task"], payload["model"])] = payload
    report = {"protocol": "All candidate artifacts were generated and SHA-256 sealed in separate jobs before this scoring job used targets. The predeclared route uses GPT-4o-mini as primary and Cohere only as missing-output fallback; no target-aware routing.", "models": list(MODELS), "tasks": {}}
    route_total = route_correct = agreement_total = agreement_correct = 0; candidate_totals = {m: [0, 0] for m in MODELS}
    for task in TASKS:
        examples = json.loads((task_root / task / "task.json").read_text())["examples"]; task_report = {"n": len(examples), "candidates": {}}; model_predictions = {}
        for model in MODELS:
            payload = sealed.get((task, model)); predictions = payload["predictions"] if payload else {}; model_predictions[model] = predictions; rows = []
            for i, example in enumerate(examples):
                pred = predictions.get(str(i)); rows.append({"index": i, "prediction": pred, "target": example["target"], "correct": pred is not None and normalized(pred) == normalized(example["target"])})
            correct = sum(r["correct"] for r in rows); candidate_totals[model][0] += correct; candidate_totals[model][1] += len(rows)
            task_report["candidates"][model] = {"correct": correct, "accuracy": correct / len(rows), "coverage": sum(r["prediction"] is not None for r in rows) / len(rows), "prediction_sha256": payload.get("prediction_sha256") if payload else None, "errors": [r for r in rows if not r["correct"]]}
        primary, fallback = model_predictions[MODELS[0]], model_predictions[MODELS[1]]; route_rows = []; agreement_rows = []
        for i, example in enumerate(examples):
            p, q = primary.get(str(i)), fallback.get(str(i)); chosen = p if p is not None else q
            route_rows.append({"index": i, "prediction": chosen, "target": example["target"], "correct": chosen is not None and normalized(chosen) == normalized(example["target"]), "source": MODELS[0] if p is not None else MODELS[1]})
            if p is not None and q is not None and normalized(p) == normalized(q): agreement_rows.append({"index": i, "prediction": p, "target": example["target"], "correct": normalized(p) == normalized(example["target"])})
        rc = sum(r["correct"] for r in route_rows); route_total += len(route_rows); route_correct += rc; agreement_total += len(agreement_rows); agreement_correct += sum(r["correct"] for r in agreement_rows)
        task_report["predeclared_route"] = {"correct": rc, "accuracy": rc / len(route_rows), "coverage": sum(r["prediction"] is not None for r in route_rows) / len(route_rows), "errors": [r for r in route_rows if not r["correct"]]}
        task_report["cross_family_agreement"] = {"n": len(agreement_rows), "coverage": len(agreement_rows) / len(examples), "correct": sum(r["correct"] for r in agreement_rows), "accuracy": sum(r["correct"] for r in agreement_rows) / len(agreement_rows) if agreement_rows else None}
        report["tasks"][task] = task_report
    report["aggregate"] = {"predeclared_route": {"n": route_total, "correct": route_correct, "micro_accuracy": route_correct / route_total}, "candidates": {m: {"n": n, "correct": c, "micro_accuracy": c / n} for m, (c, n) in candidate_totals.items()}, "cross_family_agreement": {"n": agreement_total, "coverage": agreement_total / route_total, "correct": agreement_correct, "accuracy": agreement_correct / agreement_total if agreement_total else None}}
    report["report_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True, default=str).encode()).hexdigest(); (out / "SEMANTIC_JURY_V2_RESULTS.json").write_text(json.dumps(report, indent=2, default=str) + "\n"); print(json.dumps(report["aggregate"], indent=2))

def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("predict"); p.add_argument("--task", required=True, choices=TASKS); p.add_argument("--model", required=True, choices=MODELS); p.add_argument("--task-root", type=pathlib.Path, default=DEFAULT_TASK_ROOT); p.add_argument("--out", type=pathlib.Path, required=True)
    s = sub.add_parser("score"); s.add_argument("--task-root", type=pathlib.Path, default=DEFAULT_TASK_ROOT); s.add_argument("--prediction-root", type=pathlib.Path, required=True); s.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args(); predict(args.task, args.model, args.task_root, args.out) if args.command == "predict" else score(args.task_root, args.prediction_root, args.out)
if __name__ == "__main__": main()
