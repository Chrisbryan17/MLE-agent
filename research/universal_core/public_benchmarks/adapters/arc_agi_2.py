from __future__ import annotations

from typing import Any, Iterable, Mapping


ARC_INSTRUCTIONS = (
    "Infer the exact deterministic transformation from each integer input grid "
    "to its output grid using only the demonstrations. Return a rectangular "
    "integer grid in the same nested-list format."
)


def validate_grid(value: Any) -> list[list[int]]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 30:
        raise ValueError("ARC grid height must be between 1 and 30")
    rows: list[list[int]] = []
    width: int | None = None
    for row in value:
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= 30:
            raise ValueError("ARC grid width must be between 1 and 30")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("ARC grid must be rectangular")
        copied: list[int] = []
        for cell in row:
            if type(cell) is not int or not 0 <= cell <= 9:
                raise ValueError("ARC grid cells must be integers from 0 through 9")
            copied.append(cell)
        rows.append(copied)
    return rows


def _pair_list(payload: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    value = payload.get(key)
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"ARC task {key} must be a non-empty list")
    pairs: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"ARC task {key} entries must be mappings")
        pairs.append(item)
    return tuple(pairs)


def arc_task_from_payload(task_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("ARC task id must be a non-empty string")
    if not isinstance(payload, Mapping):
        raise ValueError("ARC task payload must be a mapping")

    demonstrations: list[dict[str, Any]] = []
    for pair in _pair_list(payload, "train"):
        if "input" not in pair or "output" not in pair:
            raise ValueError("ARC training pairs require input and output")
        demonstrations.append(
            {
                "input": validate_grid(pair["input"]),
                "output": validate_grid(pair["output"]),
            }
        )

    hidden_inputs: list[list[list[int]]] = []
    for pair in _pair_list(payload, "test"):
        if "input" not in pair:
            raise ValueError("ARC test pairs require input")
        hidden_inputs.append(validate_grid(pair["input"]))

    return {
        "task_id": task_id,
        "instructions": ARC_INSTRUCTIONS,
        "demonstrations": tuple(demonstrations),
        "hidden_inputs": tuple(hidden_inputs),
    }


def accepted_grid(prediction: Mapping[str, Any]) -> list[list[int]] | None:
    if not isinstance(prediction, Mapping) or prediction.get("status") != "ACCEPTED":
        return None
    try:
        return validate_grid(prediction.get("prediction"))
    except ValueError:
        return None


def _detached(grid: list[list[int]]) -> list[list[int]]:
    return [list(row) for row in grid]


def build_submission(
    task_results: Iterable[Mapping[str, Any]],
    *,
    fallback_grid: Any = ((0,),),
) -> dict[str, list[dict[str, list[list[int]]]]]:
    fallback = validate_grid(fallback_grid)
    submission: dict[str, list[dict[str, list[list[int]]]]] = {}
    for result in task_results:
        if not isinstance(result, Mapping):
            raise ValueError("ARC task result must be a mapping")
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("ARC task result requires a non-empty task id")
        if task_id in submission:
            raise ValueError(f"duplicate ARC task id: {task_id}")
        raw_predictions = result.get("predictions")
        if not isinstance(raw_predictions, (list, tuple)):
            raise ValueError("ARC task result predictions must be a list")
        attempts: list[dict[str, list[list[int]]]] = []
        for prediction in raw_predictions:
            grid = accepted_grid(prediction) if isinstance(prediction, Mapping) else None
            chosen = fallback if grid is None else grid
            attempts.append(
                {
                    "attempt_1": _detached(chosen),
                    "attempt_2": _detached(chosen),
                }
            )
        submission[task_id] = attempts
    return submission
