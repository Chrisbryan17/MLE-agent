from __future__ import annotations

import json
from pathlib import Path

import pytest

from bbeh_evidence_protocol import (
    canonical_json_bytes,
    generate_predictions,
    score_predictions,
    write_sha256_manifest,
)


def test_canonical_json_is_stable_across_key_order() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_generation_never_reads_target(tmp_path: Path) -> None:
    class GuardedExample(dict):
        def __getitem__(self, key: str):
            if key == "target":
                raise AssertionError("target accessed during generation")
            return super().__getitem__(key)

    examples = [GuardedExample(input="q", target="proved")]
    payload = generate_predictions(examples, lambda _: "proved", "demo", tmp_path, {})
    assert payload["rows"][0]["prediction"] == "proved"


def test_score_rejects_modified_prediction_bytes(tmp_path: Path) -> None:
    examples = [{"input": "x", "target": "yes"}]
    generate_predictions(examples, lambda _: "yes", "demo", tmp_path, {})
    path = tmp_path / "predictions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rows"][0]["prediction"] = "no"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="prediction seal mismatch"):
        score_predictions(examples, path, tmp_path / "predictions.sha256", tmp_path / "first_score.json")


def test_scoring_verifies_row_identity(tmp_path: Path) -> None:
    examples = [{"input": "x", "target": "yes"}]
    generate_predictions(examples, lambda _: "yes", "demo", tmp_path, {})
    path = tmp_path / "predictions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rows"][0]["input_sha256"] = "0" * 64
    raw = canonical_json_bytes(payload)
    path.write_bytes(raw)
    (tmp_path / "predictions.sha256").write_text(__import__("hashlib").sha256(raw).hexdigest() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="prediction/input mismatch"):
        score_predictions(examples, path, tmp_path / "predictions.sha256", tmp_path / "first_score.json")


def test_manifest_hashes_all_regular_files_except_itself(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")
    manifest = write_sha256_manifest(tmp_path)
    assert set(manifest) == {"a.txt", "sub/b.txt"}
    saved = json.loads((tmp_path / "SHA256.json").read_text(encoding="utf-8"))
    assert saved == manifest
