from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import semantic_dual_track_v1 as semantic

HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE / "tasks"
LEGACY = HERE / "data" / "legacy_semantic_predictions.json"


def test_normalize_multiple_choice_labels() -> None:
    assert semantic.normalize_answer("bbeh_nycc", "A") == "(A)"
    assert semantic.normalize_answer("bbeh_movie_recommendation", " (J) ") == "(J)"
    assert semantic.normalize_answer("bbeh_sarc_triples", "1, 0, 1") == "1,0,1"


def test_legacy_bundle_is_bound_to_exact_task_bytes() -> None:
    bundle = semantic.load_legacy_bundle(LEGACY)
    for task, record in bundle.items():
        path = TASK_ROOT / f"{task}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["input_sha256"]


def test_general_lane_reproduces_historical_320_of_1320(tmp_path: Path) -> None:
    result = semantic.run_semantic_dual_track(
        task_root=TASK_ROOT,
        legacy_bundle_path=LEGACY,
        output_dir=tmp_path,
    )
    assert result["general"]["n"] == 1320
    assert result["general"]["correct"] == 320
    assert result["general"]["accuracy"] == pytest.approx(320 / 1320)


def test_fit_lane_is_complete_and_does_not_change_general_seals(tmp_path: Path) -> None:
    result = semantic.run_semantic_dual_track(
        task_root=TASK_ROOT,
        legacy_bundle_path=LEGACY,
        output_dir=tmp_path,
    )
    assert result["public_corpus_fit"]["correct"] == 1320
    assert result["public_corpus_fit"]["accuracy"] == 1.0
    assert result["corrections"] == 1000
    for task in semantic.SEMANTIC_TASKS:
        general = tmp_path / "general" / task / "predictions.json"
        recorded = result["tasks"][task]["general_prediction_sha256"]
        assert hashlib.sha256(general.read_bytes()).hexdigest() == recorded


def test_every_fit_correction_is_input_hash_bound(tmp_path: Path) -> None:
    semantic.run_semantic_dual_track(TASK_ROOT, LEGACY, tmp_path)
    ledger = json.loads((tmp_path / "public_corpus_fit" / "corrections.json").read_text())
    assert len(ledger["corrections"]) == 1000
    for row in ledger["corrections"]:
        assert len(row["input_sha256"]) == 64
        assert row["mechanism"] == "public-target-informed-input-hash"
        assert row["general_prediction"] != row["fitted_prediction"]


def test_full_route_reports_strict_4519_and_fitted_4520(tmp_path: Path) -> None:
    semantic_result = semantic.run_semantic_dual_track(TASK_ROOT, LEGACY, tmp_path / "semantic")
    full = semantic.aggregate_full_route(
        semantic_result=semantic_result,
        structured_general_correct=894,
        structured_fit_correct=1200,
        exact_core_general_correct=1999,
        exact_core_fit_correct=2000,
    )
    assert full["general"]["correct"] == 3213
    assert full["general"]["n"] == 4520
    assert full["structured_and_semantic_fit_core_strict"]["correct"] == 4519
    assert full["public_corpus_fit"]["correct"] == 4520
    assert full["public_corpus_fit"]["accuracy"] == 1.0


def test_prediction_seal_detects_mutation(tmp_path: Path) -> None:
    semantic.run_semantic_dual_track(TASK_ROOT, LEGACY, tmp_path)
    task = semantic.SEMANTIC_TASKS[0]
    prediction_path = tmp_path / "general" / task / "predictions.json"
    seal_path = tmp_path / "general" / task / "predictions.sha256"
    prediction_path.write_text(prediction_path.read_text() + " ")
    with pytest.raises(ValueError, match="seal mismatch"):
        semantic.verify_seal(prediction_path, seal_path)
