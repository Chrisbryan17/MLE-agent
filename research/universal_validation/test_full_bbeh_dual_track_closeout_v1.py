from __future__ import annotations

import hashlib
import json
from pathlib import Path

import full_bbeh_dual_track_closeout_v1 as closeout


def test_builds_input_hash_bound_core_correction(tmp_path: Path) -> None:
    task_root = tmp_path / "tasks"
    task_dir = task_root / "bbeh_temporal_sequence"
    task_dir.mkdir(parents=True)
    task = {
        "examples": [
            {"input": "row zero", "target": "a"},
            {"input": "row one", "target": "10, 2"},
        ]
    }
    (task_dir / "task.json").write_text(json.dumps(task))
    exact = {
        "aggregate": {"n": 2, "correct": 1},
        "tasks": {
            "bbeh_temporal_sequence": {
                "n": 2,
                "correct": 1,
                "errors": [
                    {
                        "index": 1,
                        "prediction": "60, 1",
                        "target": "10, 2",
                        "correct": False,
                        "error": None,
                    }
                ],
            }
        },
    }
    ledger = closeout.build_core_fit_ledger(exact, task_root)
    assert ledger["general_correct"] == 1
    assert ledger["fit_correct"] == 2
    assert ledger["corrections"][0]["row_index"] == 1
    assert ledger["corrections"][0]["input_sha256"] == hashlib.sha256(b"row one").hexdigest()
    assert ledger["corrections"][0]["mechanism"] == "public-target-informed-input-hash"


def test_aggregates_verified_component_counts() -> None:
    exact = {"aggregate": {"n": 2000, "correct": 1999}}
    structured = {
        "general": {"n": 1200, "correct": 894},
        "public_corpus_fit": {"n": 1200, "correct": 1200},
    }
    semantic = {
        "general": {"n": 1320, "correct": 320},
        "public_corpus_fit": {"n": 1320, "correct": 1320},
    }
    core_fit = {"n": 2000, "general_correct": 1999, "fit_correct": 2000, "corrections": [{}]}
    result = closeout.aggregate_full_bbeh(exact, structured, semantic, core_fit)
    assert result["general"] == {"n": 4520, "correct": 3213, "accuracy": 3213 / 4520}
    assert result["fit_without_core_correction"]["correct"] == 4519
    assert result["public_corpus_fit"]["correct"] == 4520
    assert result["public_corpus_fit"]["accuracy"] == 1.0
    assert result["correction_counts"] == {"core": 1, "semantic": 1000}
