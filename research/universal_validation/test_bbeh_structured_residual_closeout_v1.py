from __future__ import annotations

import hashlib
import json

import bbeh_structured_residual_closeout_v1 as closeout


def test_prediction_artifact_excludes_targets_and_is_hash_sealed(tmp_path) -> None:
    examples = [
        {"input": "prompt-a", "target": "1"},
        {"input": "prompt-b", "target": "2"},
    ]
    prediction_path = tmp_path / "predictions.json"
    seal_path = tmp_path / "predictions.sha256"

    closeout.generate_predictions(
        examples,
        solver=lambda prompt: {"prompt-a": "1", "prompt-b": None}[prompt],
        prediction_path=prediction_path,
        seal_path=seal_path,
    )

    raw = prediction_path.read_bytes()
    payload = json.loads(raw)
    assert payload["protocol"] == "targets-hidden-during-generation"
    assert payload["rows"][0]["prediction"] == "1"
    assert payload["rows"][1]["prediction"] is None
    assert all("target" not in row for row in payload["rows"])
    assert seal_path.read_text().strip() == hashlib.sha256(raw).hexdigest()


def test_scoring_requires_unchanged_prediction_seal(tmp_path) -> None:
    examples = [{"input": "prompt-a", "target": "1"}]
    prediction_path = tmp_path / "predictions.json"
    seal_path = tmp_path / "predictions.sha256"
    score_path = tmp_path / "first_score.json"
    closeout.generate_predictions(examples, lambda _: "1", prediction_path, seal_path)
    prediction_path.write_text(prediction_path.read_text() + "\n")

    try:
        closeout.score_predictions(examples, prediction_path, seal_path, score_path)
    except ValueError as exc:
        assert "seal mismatch" in str(exc).lower()
    else:
        raise AssertionError("tampered predictions were scored")


def test_first_score_counts_abstentions_and_exceptions_wrong(tmp_path) -> None:
    examples = [
        {"input": "a", "target": "1"},
        {"input": "b", "target": "2"},
        {"input": "c", "target": "3"},
    ]
    prediction_path = tmp_path / "predictions.json"
    seal_path = tmp_path / "predictions.sha256"
    score_path = tmp_path / "first_score.json"

    def solver(prompt: str):
        if prompt == "a":
            return "1"
        if prompt == "b":
            return None
        raise RuntimeError("parser gap")

    closeout.generate_predictions(examples, solver, prediction_path, seal_path)
    score = closeout.score_predictions(examples, prediction_path, seal_path, score_path)

    assert score["n"] == 3
    assert score["correct"] == 1
    assert score["answered"] == 1
    assert score["errors"] == 1
    assert score["accuracy"] == 1 / 3
    assert score["coverage"] == 1 / 3


def test_grammar_audit_reports_uncompiled_clues_without_targets() -> None:
    examples = [
        {
            "input": """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Using the clues provided below, answer the question at the end.
Clue 1: Alice is immediately to the left of Bob.
Clue 2: Alice is two spaces away from Cara.
Question: What position is Alice at?""",
            "target": "1",
        }
    ]

    audit = closeout.audit_zebra_grammar(examples)

    assert audit["examples"] == 1
    assert audit["clues"] == 2
    assert audit["compiled_clues"] == 1
    assert audit["uncompiled_clues"] == 1
    assert audit["errors"][0]["clue_index"] == 1
    assert "two spaces away" in audit["errors"][0]["clue"]
    assert all("target" not in row for row in audit["errors"])
