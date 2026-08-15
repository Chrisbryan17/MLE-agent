from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "symmetry_complete"
_EXPECTED_SHA256 = {
    "496994bd.json": "ecc40bb943911e33cdfc1e668a5bb49b22ad55a662aa37d68ba57e884897dc25",
    "b8825c91.json": "ccf892a7ba8797ab4c69b241d80dd389cde0b9c7b8c0667a8b3a273873c4d49d",
    "e729b7be.json": "d2565e3c8e6482a1a3cec2ccf604032c223ee6d6f579dfee98a72b4cbdc12c99",
    "f25ffba3.json": "98bd5da81220ac72cf0a2d8ae093ed602066e14cb28ffce6db3110d91382067c",
}


def test_symmetry_complete_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
