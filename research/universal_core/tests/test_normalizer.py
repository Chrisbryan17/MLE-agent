from __future__ import annotations

import pytest

from universal_core.normalizer import normalize_task_payload


def _demos():
    return [
        {"input": [["a", 2], ["b", 1]], "output": [["b", 1], ["a", 2]]},
        {"input": [["c", 3], ["d", 0]], "output": [["d", 0], ["c", 3]]},
        {"input": [["e", 8], ["f", 4]], "output": [["f", 4], ["e", 8]]},
    ]


def test_normalizer_preserves_row_order_and_metadata() -> None:
    payload = {
        "task_name": "secret_benchmark_route",
        "instructions": "Return the records sorted by score.",
        "demonstrations": _demos(),
        "hidden_inputs": [[["x", 7], ["y", 5]]],
    }
    package = normalize_task_payload(payload)
    assert package.hidden_inputs[0][0][0] == "x"
    assert package.metadata["task_name"] == "secret_benchmark_route"


def test_normalizer_accepts_aliases_and_unwraps_input_only_rows() -> None:
    package = normalize_task_payload(
        {
            "prompt": "Sort records.",
            "examples": _demos(),
            "test_inputs": [{"input": [["x", 9], ["y", 3]]}],
            "output_schema": {"kind": "list"},
        }
    )
    assert package.instructions == "Sort records."
    assert package.hidden_inputs == ([["x", 9], ["y", 3]],)
    assert package.output_schema.kind == "list"


def test_normalizer_rejects_hidden_labels() -> None:
    payload = {
        "instructions": "Classify.",
        "demonstrations": [{"input": i, "output": i} for i in range(3)],
        "hidden_inputs": [{"input": 9, "label": 9}],
    }
    with pytest.raises(ValueError, match="hidden target"):
        normalize_task_payload(payload)


def test_normalizer_rejects_conflicting_aliases() -> None:
    with pytest.raises(ValueError, match="conflicting aliases"):
        normalize_task_payload(
            {
                "instructions": "one",
                "prompt": "two",
                "demonstrations": _demos(),
                "hidden_inputs": [1],
            }
        )
