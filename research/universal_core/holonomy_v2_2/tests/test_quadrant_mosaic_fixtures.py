from __future__ import annotations

import hashlib
from pathlib import Path


_FIXTURES = Path(__file__).parent / "fixtures" / "quadrant_mosaic"
_EXPECTED_SHA256 = {
    "0c786b71.json": "df8a0f7356a4b200d7c9a4d8f58d40662f01563ebb25c85f67c718bdb487a3f2",
    "3af2c5a8.json": "969747e767a1af9f23689cc7e262abaadccf1e02ff8c2a446f738daaa4a24a48",
    "46442a0e.json": "cd58b40fb6c991567f666e2d42a98a8a5ba9de6708011d3ffb36245487aba5ba",
    "62c24649.json": "bd4124704f8b1b02038f80c7cb1187224d1daf4dd528cea940486bb294b48dc4",
    "67e8384a.json": "3ad82285fa52a72081cfb705f80a224cf4f984232a1e002421d12b38b83a012d",
    "7953d61e.json": "789c244eae24dc51956ed3beea9b530b9af8d895692b384bd6fa3eb04e3e6f12",
    "7fe24cdd.json": "6deb4aa52a4cc3d63cf8b8b99846e50297837910a1b9c6d60f7e028cee8c68d7",
    "833dafe3.json": "c3c9b31eb8def554991acfc0be966e49cb128568a5f948452be5b9bda1ce9dd2",
    "ed98d772.json": "f7f2569ee2b94b6e4d98ff72e3f36ff83441a802f3bc7c19ea8c04c81108b18b",
}


def test_quadrant_mosaic_fixtures_match_pinned_training_payloads() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(_FIXTURES.glob("*.json"))
    }

    assert actual == _EXPECTED_SHA256
