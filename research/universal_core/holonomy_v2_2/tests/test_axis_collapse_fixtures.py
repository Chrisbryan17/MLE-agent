from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "axis_collapse"
_EXPECTED_SHA256 = {
    "2dee498d.json": "38e27a5c17bf593547182b8914cf044052b158ebe4c5e802d14fb6af11458388",
    "746b3537.json": "2fa42394d0d48c4c9534aac1ce000ab97ff804f9d69a34d16126f6a17a757686",
    "7b7f7511.json": "28480a33bbe9ff487d845a62a7c21f3d5bc2d1de493a5f91e0c19b57b1aa1d60",
    "ce8d95cc.json": "728025ba05aacc3b678ecd7a75d605bf8d9477c2bcd2b667e031c32406233c41",
    "e1baa8a4.json": "16411bc668a55e51401716d4fc48424413443a8b21f97a670ce14df9ba325f9d",
    "eb5a1d5d.json": "96a1772a93e9cecf1050532b031ad3605390cc5c907cb4b919d4e095eee2f54d",
}


def test_axis_collapse_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
