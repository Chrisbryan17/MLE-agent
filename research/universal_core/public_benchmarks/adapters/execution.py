from __future__ import annotations

from typing import Any, Iterable, Mapping

from research.universal_core.holonomy_v2.blind_adapter import run_public_task_v2

from .arc_agi_2 import arc_task_from_payload, build_submission, score_result as score_arc
from .bbeh import bbeh_task_from_payload, score_result as score_bbeh
from .livebench import livebench_task_from_rows, score_result as score_livebench


def run_arc_payload(
    task_id: str,
    payload: Mapping[str, Any],
    engine: Any,
) -> dict[str, Any]:
    task = arc_task_from_payload(task_id, payload)
    raw_result = run_public_task_v2(task, engine)
    submission = build_submission((raw_result,))[task_id]
    return {
        "benchmark": "arc_agi_2",
        "task_id": task_id,
        "raw_result": raw_result,
        "submission": submission,
        "metrics": score_arc(task_id, payload, raw_result),
    }


def run_bbeh_payload(
    task_name: str,
    payload: Mapping[str, Any],
    engine: Any,
    *,
    demonstration_count: int,
    offset: int = 0,
) -> dict[str, Any]:
    prepared = bbeh_task_from_payload(
        task_name,
        payload,
        demonstration_count=demonstration_count,
        offset=offset,
    )
    raw_result = run_public_task_v2(prepared.task, engine)
    return {
        "benchmark": "bbeh_transfer",
        "task_id": task_name,
        "demonstration_count": demonstration_count,
        "offset": offset,
        "hidden_example_indices": list(prepared.example_indices),
        "raw_result": raw_result,
        "metrics": score_bbeh(prepared, raw_result),
    }


def run_livebench_rows(
    rows: Iterable[Mapping[str, Any]],
    engine: Any,
    *,
    demonstration_count: int,
    offset: int = 0,
) -> dict[str, Any]:
    prepared = livebench_task_from_rows(
        rows,
        demonstration_count=demonstration_count,
        offset=offset,
    )
    raw_result = run_public_task_v2(prepared.task, engine)
    return {
        "benchmark": "livebench_scalar_transfer",
        "task_id": prepared.task["task_id"],
        "category": prepared.category,
        "family": prepared.family,
        "demonstration_count": demonstration_count,
        "offset": offset,
        "hidden_question_ids": list(prepared.question_ids),
        "raw_result": raw_result,
        "metrics": score_livebench(prepared, raw_result),
    }
