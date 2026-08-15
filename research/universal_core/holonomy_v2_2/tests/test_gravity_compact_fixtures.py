from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "gravity_compact"
_EXPECTED_SHA256 = {
    "1e0a9b12.json": "6a71dbedc8403bd28fa76bd8b472597a8ecaab3af31151a2a3b72baeadd5e617",
    "3906de3d.json": "b4c20d433380e00840a75c6976ad0d0fabd80e052ab77b47422d64b1cae5f6dc",
}


def test_gravity_compact_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
