from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.blind_adapter import run_public_task_v2
from universal_core.holonomy_v2.engine import HolonomyEngine
from universal_core.holonomy_v2.types import SearchConfig


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


class RecordingEngine(HolonomyEngine):
    def __init__(self) -> None:
        super().__init__(SearchConfig())
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def induce(self, instructions: str, demonstrations: tuple[Any, ...]):
        self.calls.append((instructions, demonstrations))
        return super().induce(instructions, demonstrations)


def test_hidden_inputs_are_not_passed_to_induction() -> None:
    package = {
        "task_id": "opaque-01",
        "instructions": "Return 2*n+1.",
        "demonstrations": [
            {"input": 1, "output": 3},
            {"input": 2, "output": 5},
            {"input": 3, "output": 7},
        ],
        "hidden_inputs": [101, 202],
    }
    engine = RecordingEngine()
    output = run_public_task_v2(package, engine)
    assert engine.calls == [(package["instructions"], tuple(package["demonstrations"]))]
    assert [item["prediction"] for item in output["predictions"]] == [203, 405]
    assert output["freeze_digest"]


def test_adapter_is_byte_stable_at_data_level() -> None:
    package = {
        "task_id": "opaque-02",
        "instructions": "Return 2*n+1.",
        "demonstrations": [
            {"input": 1, "output": 3},
            {"input": 2, "output": 5},
            {"input": 3, "output": 7},
        ],
        "hidden_inputs": [4, 5],
    }
    first = run_public_task_v2(package, HolonomyEngine(SearchConfig()))
    second = run_public_task_v2(package, HolonomyEngine(SearchConfig()))
    assert first == second
