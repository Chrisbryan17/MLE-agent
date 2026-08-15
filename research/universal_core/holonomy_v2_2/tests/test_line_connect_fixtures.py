from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "line_connect"
_EXPECTED_SHA256 = {
    "1f876c06.json": "b53a1a25685895400323e813a373f0a66fc9512f7dbbb326d52a93695fca8143",
    "22168020.json": "d067b4f83f84120300310199e3a95c65258edcc53d8b0f425288d7ddb71a962e",
    "22eb0ac0.json": "cf37cc34e7b0aa123c2806eca77a7d9916b50afea4e6e2db71d5149fe1f1af0d",
    "ded97339.json": "fd14b4ee37bb1539c26a79abed743626b37f5935794ce82cbd0b3332c207906e",
}


def test_line_connect_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
