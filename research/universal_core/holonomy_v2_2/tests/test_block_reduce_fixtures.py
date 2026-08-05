from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "block_reduce"
_EXPECTED_SHA256 = {
    "5614dbcf.json": "0751d867504f022964f0d4ef909ae9e68c928f499841f6a3e8b7143791fca53e",
    "68b67ca3.json": "767e0baf6a71a7f288ab5a08f13a4ecc65ac5a43144586dec0c3ccd2eff5edb4",
}


def test_block_reduce_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }
    assert actual == _EXPECTED_SHA256
