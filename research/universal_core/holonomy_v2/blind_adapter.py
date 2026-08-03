from __future__ import annotations

from typing import Any, Mapping

from .engine import HolonomyEngine


def _get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value[key]
    return getattr(value, key)


def run_public_task_v2(task: Any, engine: HolonomyEngine) -> dict[str, Any]:
    instructions = str(_get(task, "instructions"))
    demonstrations = tuple(_get(task, "demonstrations"))
    hidden_inputs = tuple(_get(task, "hidden_inputs"))
    result = engine.induce(instructions, demonstrations)
    task_id = str(_get(task, "task_id"))
    if result.program is None:
        status = "LOW_EVIDENCE" if result.abstention is None else result.abstention.code.value
        predictions = tuple({"status": status, "prediction": None} for _ in hidden_inputs)
        return {
            "task_id": task_id,
            "tier": engine.config.tier,
            "program_digest": None,
            "freeze_digest": None,
            "prediction_digest": None,
            "evidence": result.evidence.to_data(),
            "predictions": list(predictions),
        }
    frozen = engine.freeze(result)
    batch = frozen.predict_all(hidden_inputs)
    return {
        "task_id": task_id,
        "tier": engine.config.tier,
        "program_digest": result.program.digest,
        "freeze_digest": frozen.freeze_digest,
        "prediction_digest": batch.prediction_digest,
        "evidence": result.evidence.to_data(),
        "predictions": [dict(item) for item in batch.predictions],
    }
