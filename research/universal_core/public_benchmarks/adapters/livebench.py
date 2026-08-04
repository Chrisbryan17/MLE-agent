from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


LIVEBENCH_INSTRUCTIONS = (
    "Infer the exact mapping from each prompt in this single LiveBench task family "
    "to its answer string using only the demonstrations. Return only the answer string."
)


@dataclass(frozen=True)
class PreparedLiveBenchTask:
    task: Mapping[str, Any]
    targets: tuple[str, ...]
    question_ids: tuple[str, ...]
    category: str
    family: str


def _row_data(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    if not isinstance(row, Mapping):
        raise ValueError("LiveBench rows must be mappings")
    question_id = row.get("question_id")
    category = row.get("category")
    family = row.get("task")
    turns = row.get("turns")
    target = row.get("ground_truth")
    if not isinstance(question_id, str) or not question_id:
        raise ValueError("LiveBench question id must be a non-empty string")
    if not isinstance(category, str) or not category:
        raise ValueError("LiveBench category must be a non-empty string")
    if not isinstance(family, str) or not family:
        raise ValueError("LiveBench task family must be a non-empty string")
    if not isinstance(turns, (list, tuple)) or len(turns) != 1 or not isinstance(turns[0], str) or not turns[0]:
        raise ValueError("LiveBench scalar adapter requires exactly one turn")
    if not isinstance(target, str) or not target:
        raise ValueError("LiveBench scalar adapter requires a deterministic string target")
    return question_id, category, family, turns[0], target


def livebench_task_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    demonstration_count: int,
    offset: int = 0,
) -> PreparedLiveBenchTask:
    parsed = tuple(_row_data(row) for row in rows)
    if len(parsed) < 2:
        raise ValueError("LiveBench scalar adapter requires at least two rows")
    category = parsed[0][1]
    family = parsed[0][2]
    if any(item[1] != category or item[2] != family for item in parsed):
        raise ValueError("LiveBench rows must share the same category and task family")
    if not isinstance(demonstration_count, int) or not 1 <= demonstration_count < len(parsed):
        raise ValueError("LiveBench demonstration count must leave at least one hidden row")
    if not isinstance(offset, int):
        raise ValueError("LiveBench offset must be an integer")

    start = offset % len(parsed)
    order = tuple(range(start, len(parsed))) + tuple(range(0, start))
    demo_indices = order[:demonstration_count]
    hidden_indices = order[demonstration_count:]

    demonstrations = tuple(
        {"input": parsed[index][3], "output": parsed[index][4]}
        for index in demo_indices
    )
    hidden_inputs = tuple(parsed[index][3] for index in hidden_indices)
    targets = tuple(parsed[index][4] for index in hidden_indices)
    question_ids = tuple(parsed[index][0] for index in hidden_indices)
    task_id = f"livebench:{category}:{family}"

    return PreparedLiveBenchTask(
        task={
            "task_id": task_id,
            "instructions": LIVEBENCH_INSTRUCTIONS,
            "demonstrations": demonstrations,
            "hidden_inputs": hidden_inputs,
        },
        targets=targets,
        question_ids=question_ids,
        category=category,
        family=family,
    )


def score_result(prepared: PreparedLiveBenchTask, result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("LiveBench result must be a mapping")
    if result.get("task_id") != prepared.task["task_id"]:
        raise ValueError("LiveBench result task id does not match prepared task")
    predictions = result.get("predictions")
    if not isinstance(predictions, (list, tuple)) or len(predictions) != len(prepared.targets):
        raise ValueError("LiveBench prediction count does not match hidden row count")

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

    total = len(prepared.targets)
    abstained = total - accepted - failed
    return {
        "task_id": prepared.task["task_id"],
        "category": prepared.category,
        "family": prepared.family,
        "rows": total,
        "correct": correct,
        "accepted": accepted,
        "abstained": abstained,
        "failed": failed,
        "incorrect_attempts": accepted - correct,
        "raw_accuracy": correct / total,
        "coverage": accepted / total,
        "attempted_accuracy": correct / accepted if accepted else 0.0,
    }
