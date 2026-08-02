from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .program import Program
from .residuals import ResidualReport
from .search import SearchResult, search_candidates
from .types import Abstention, SearchConfig


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=repr) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _demo_data(item: Any) -> dict[str, Any]:
    if hasattr(item, "input") and hasattr(item, "output"):
        return {"input": item.input, "output": item.output}
    if isinstance(item, Mapping):
        return {"input": item["input"], "output": item["output"]}
    raise TypeError("demonstration must provide input and output")


@dataclass(frozen=True)
class EngineEvidence:
    tier: str
    config: Mapping[str, Any]
    induction_digest: str
    program_digest: str | None
    residual_digest: str | None
    search_stats: Mapping[str, Any]
    digest: str

    @classmethod
    def build(
        cls,
        *,
        tier: str,
        config: SearchConfig,
        induction_digest: str,
        program: Program | None,
        report: ResidualReport | None,
        search: SearchResult,
    ) -> "EngineEvidence":
        body = {
            "tier": tier,
            "config": config.to_data(),
            "induction_digest": induction_digest,
            "program_digest": None if program is None else program.digest,
            "residual_digest": None if report is None else report.digest,
            "search_stats": search.stats.to_data(),
        }
        return cls(digest=_digest(body), **body)

    def to_data(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "config": dict(self.config),
            "induction_digest": self.induction_digest,
            "program_digest": self.program_digest,
            "residual_digest": self.residual_digest,
            "search_stats": dict(self.search_stats),
            "digest": self.digest,
        }


@dataclass(frozen=True)
class InductionResult:
    program: Program | None
    report: ResidualReport | None
    abstention: Abstention | None
    evidence: EngineEvidence


@dataclass(frozen=True)
class PredictionBatch:
    predictions: tuple[Mapping[str, Any], ...]
    freeze_digest: str
    prediction_digest: str

    def to_data(self) -> dict[str, Any]:
        return {
            "predictions": [dict(item) for item in self.predictions],
            "freeze_digest": self.freeze_digest,
            "prediction_digest": self.prediction_digest,
        }


@dataclass(frozen=True)
class FrozenProgram:
    program: Program
    evidence_digest: str
    freeze_digest: str

    def predict_all(self, hidden_inputs: Iterable[Any]) -> PredictionBatch:
        if not self.freeze_digest:
            raise RuntimeError("program must be frozen before prediction")
        predictions: list[dict[str, Any]] = []
        for value in hidden_inputs:
            try:
                prediction = self.program.run(value)
                predictions.append({"status": "ACCEPTED", "prediction": prediction})
            except Exception as exc:
                predictions.append({
                    "status": "EXECUTION_FAILED",
                    "prediction": None,
                    "error": type(exc).__name__,
                })
        body = {
            "freeze_digest": self.freeze_digest,
            "predictions": predictions,
        }
        return PredictionBatch(tuple(predictions), self.freeze_digest, _digest(body))


class HolonomyEngine:
    def __init__(self, config: SearchConfig) -> None:
        self.config = config

    def induce(self, instructions: str, demonstrations: tuple[Any, ...]) -> InductionResult:
        demo_data = [_demo_data(item) for item in demonstrations]
        induction_digest = _digest({
            "instructions": instructions,
            "demonstrations": demo_data,
            "config": self.config.to_data(),
        })
        search = search_candidates(instructions, demonstrations, self.config)
        evidence = EngineEvidence.build(
            tier=self.config.tier,
            config=self.config,
            induction_digest=induction_digest,
            program=search.program,
            report=search.report,
            search=search,
        )
        return InductionResult(search.program, search.report, search.abstention, evidence)

    def freeze(self, result: InductionResult) -> FrozenProgram:
        if result.program is None or result.report is None or not result.report.mandatory_pass:
            raise ValueError("only an accepted program may be frozen")
        body = {
            "program_digest": result.program.digest,
            "evidence_digest": result.evidence.digest,
            "residual_digest": result.report.digest,
        }
        return FrozenProgram(result.program, result.evidence.digest, _digest(body))
