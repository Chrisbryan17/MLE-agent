from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "palette_repeat"
_EXPECTED_SHA256 = {
    "a59b95c0.json": "138f5638ba814834e4f222d6509665ea091c36be6bfc9305fdf41fecd72c41a1",
    "ac0a08a4.json": "5e68feb78f2f5405be84063528e4beab2b66b8b8cbdac211e305d75e8ac8703d",
    "b91ae062.json": "dfb1b3e1b6d275cb1830c1d42320358a1ddc45a925504904ff07fa0dac8a2a53",
    "d4b1c2b1.json": "46b0f9fec811ac831b916e44ef8269e45e2b054d59354a4a8f8a1a299716d753",
}


def test_palette_repeat_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
