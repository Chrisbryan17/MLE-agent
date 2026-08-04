from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


BBEH_INSTRUCTIONS = (
    "Infer the exact mapping from each prompt in this single BBEH task family "
    "to its target string using only the demonstrations. Return only the target string."
)


@dataclass(frozen=True)
class PreparedBBEHTask:
    task: Mapping[str, Any]
    targets: tuple[str, ...]
    example_indices: tuple[int, ...]


def _examples(payload: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    if not isinstance(payload, Mapping):
        raise ValueError("BBEH payload must be a mapping")
    raw = payload.get("examples")
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise ValueError("BBEH payload requires at least two examples")
    examples: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("BBEH examples must be mappings")
        prompt = item.get("input")
        target = item.get("target")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("BBEH example input must be a non-empty string")
        if not isinstance(target, str) or not target:
            raise ValueError("BBEH example target must be a non-empty string")
        examples.append((prompt, target))
    return tuple(examples)


def bbeh_task_from_payload(
    task_name: str,
    payload: Mapping[str, Any],
    *,
    demonstration_count: int,
    offset: int = 0,
) -> PreparedBBEHTask:
    if not isinstance(task_name, str) or not task_name:
        raise ValueError("BBEH task name must be a non-empty string")
    examples = _examples(payload)
    if not isinstance(demonstration_count, int) or not 1 <= demonstration_count < len(examples):
        raise ValueError("BBEH demonstration count must leave at least one hidden row")
    if not isinstance(offset, int):
        raise ValueError("BBEH offset must be an integer")

    start = offset % len(examples)
    order = tuple(range(start, len(examples))) + tuple(range(0, start))
    demo_indices = order[:demonstration_count]
    hidden_indices = order[demonstration_count:]

    demonstrations = tuple(
        {"input": examples[index][0], "output": examples[index][1]}
        for index in demo_indices
    )
    hidden_inputs = tuple(examples[index][0] for index in hidden_indices)
    targets = tuple(examples[index][1] for index in hidden_indices)

    return PreparedBBEHTask(
        task={
            "task_id": task_name,
            "instructions": BBEH_INSTRUCTIONS,
            "demonstrations": demonstrations,
            "hidden_inputs": hidden_inputs,
        },
        targets=targets,
        example_indices=hidden_indices,
    )


def score_result(prepared: PreparedBBEHTask, result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("BBEH result must be a mapping")
    if result.get("task_id") != prepared.task["task_id"]:
        raise ValueError("BBEH result task id does not match prepared task")
    predictions = result.get("predictions")
    if not isinstance(predictions, (list, tuple)) or len(predictions) != len(prepared.targets):
        raise ValueError("BBEH prediction count does not match hidden row count")

    correct = 0
    accepted = 0
    failed = 0
    for target, item in zip(prepared.targets, predictions):
        if not isinstance(item, Mapping):
            failed += 1
            continue
        status = item.get("status")
        if status == "ACCEPTED":
            accepted += 1
            if item.get("prediction") == target:
                correct += 1
        elif status == "EXECUTION_FAILED" or (isinstance(status, str) and status.endswith("_FAILED")):
            failed += 1

    rows = len(prepared.targets)
    abstained = rows - accepted - failed
    incorrect_attempts = accepted - correct
    return {
        "task_id": prepared.task["task_id"],
        "rows": rows,
        "correct": correct,
        "accepted": accepted,
        "abstained": abstained,
        "failed": failed,
        "incorrect_attempts": incorrect_attempts,
        "raw_accuracy": correct / rows,
        "coverage": accepted / rows,
        "attempted_accuracy": correct / accepted if accepted else 0.0,
    }
