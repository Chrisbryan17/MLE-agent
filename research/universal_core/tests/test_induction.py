from __future__ import annotations

import pytest

from universal_core.induction import (
    HeuristicProposalBackend,
    JsonProposalBackend,
    build_induction_view,
)


def test_induction_view_excludes_metadata(task_package) -> None:
    view = build_induction_view(task_package)
    assert "task_name" not in view
    assert "metadata" not in view
    assert task_package.metadata["task_name"] == "randomized-name"


def test_heuristic_backend_infers_sort_records(task_package) -> None:
    proposals = HeuristicProposalBackend().propose(
        task_package.instructions,
        task_package.demonstrations,
        task_package.output_schema,
    )
    assert any(
        p.program_data["kind"] == "operator_program"
        and p.program_data["steps"][0]["operator"] == "sort_records"
        and p.program_data["steps"][0]["arguments"]["field"] == 1
        for p in proposals
    )


def test_heuristic_backend_infers_affine_transform(affine_package) -> None:
    proposals = HeuristicProposalBackend().propose(
        affine_package.instructions,
        affine_package.demonstrations,
        affine_package.output_schema,
    )
    matches = [p for p in proposals if p.program_data.get("template") == "affine"]
    assert len(matches) == 1
    assert matches[0].program_data["parameters"] == {"a": 3, "b": 2}


def test_json_backend_rejects_untyped_model_output(task_package) -> None:
    backend = JsonProposalBackend(lambda _: '{"program": "run arbitrary python"}')
    with pytest.raises(ValueError, match="proposal schema"):
        backend.propose("sort", task_package.demonstrations, task_package.output_schema)


def test_json_backend_rejects_unknown_operator(task_package) -> None:
    payload = '''{
      "proposals": [{
        "spec": {"input_type": "LIST", "output_type": "LIST", "capabilities": ["SORT"], "objective": "sort"},
        "program": {"kind": "operator_program", "version": 1, "steps": [
          {"operator": "private_benchmark_route", "source": "$input", "target": "$output", "arguments": {}}
        ]},
        "confidence": 0.9
      }]
    }'''
    backend = JsonProposalBackend(lambda _: payload)
    with pytest.raises(ValueError, match="unknown operator"):
        backend.propose("sort", task_package.demonstrations, task_package.output_schema)


def test_heuristic_backend_composes_filter_then_count() -> None:
    from universal_core.contracts import Demonstration, OutputSchema

    demonstrations = (
        Demonstration([["a", 2], ["b", 5], ["c", 8]], 2),
        Demonstration([["d", 1], ["e", 9], ["f", 7]], 2),
        Demonstration([["g", 6], ["h", 4], ["i", 10]], 2),
    )
    proposals = HeuristicProposalBackend().propose("Count scores at least five.", demonstrations, OutputSchema(kind="integer"))
    assert any(
        [step["operator"] for step in proposal.program_data.get("steps", [])]
        == ["filter_compare", "count"]
        for proposal in proposals
    )


def test_heuristic_backend_infers_discriminative_keyword_classifier() -> None:
    from universal_core.contracts import Demonstration, OutputSchema

    demonstrations = (
        Demonstration("urgent red incident", "alert"),
        Demonstration("red system failure", "alert"),
        Demonstration("calm blue status", "normal"),
        Demonstration("blue routine update", "normal"),
    )
    proposals = HeuristicProposalBackend().propose("Classify the status.", demonstrations, OutputSchema(kind="string"))
    classifier = next(p for p in proposals if p.program_data.get("template") == "keyword_relation")
    assert classifier.program_data["parameters"]["rules"] == [
        {"token": "red", "label": "alert"},
        {"token": "blue", "label": "normal"},
    ]
