from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.engine import HolonomyEngine
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_freeze_precedes_hidden_prediction() -> None:
    engine = HolonomyEngine(SearchConfig())
    result = engine.induce("Return 2*n+1.", (Demo(1, 3), Demo(2, 5), Demo(3, 7)))
    assert result.program is not None
    frozen = engine.freeze(result)
    assert frozen.freeze_digest
    batch = frozen.predict_all((4, 5))
    assert [item["prediction"] for item in batch.predictions] == [9, 11]
    assert batch.freeze_digest == frozen.freeze_digest


def test_engine_evidence_is_deterministic() -> None:
    demos = (Demo(1, 3), Demo(2, 5), Demo(3, 7))
    engine = HolonomyEngine(SearchConfig())
    left = engine.induce("Return 2*n+1.", demos)
    right = engine.induce("Return 2*n+1.", demos)
    assert left.evidence.digest == right.evidence.digest
    assert left.program is not None and right.program is not None
    assert left.program.digest == right.program.digest


def test_unsupported_task_returns_typed_abstention() -> None:
    engine = HolonomyEngine(SearchConfig())
    result = engine.induce("Return an unknown transform.", (Demo({"x": 1}, "z"),))
    assert result.program is None
    assert result.abstention is not None
