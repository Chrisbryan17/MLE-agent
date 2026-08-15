from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "ray_extend"
_EXPECTED_SHA256 = {
    "623ea044.json": "578ab7e47a2d67489f1103715615f719ef81e9faf773be85586803d6da44cbdd",
    "d037b0a7.json": "9e39a4acdb3e3bff7dd54bed5f4ab77973f4027d48beb62a9c740d8a7a0b0aee",
}


def test_ray_extend_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
