#!/usr/bin/env python3
from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
B64_PATH = HERE / "data" / "legacy_semantic_predictions.json.gz.b64"
OUT_PATH = HERE / "data" / "legacy_semantic_predictions.json"
EXPECTED_B64_SHA256 = "8593c12b2b6c5c7e4a127373831332097289e147d8964a449cb39fef5235c8af"
EXPECTED_GZIP_SHA256 = "8935b6ac563d14d58eb3d62192eb962d6debcb27c19250fbeff7127b74d13b4f"
EXPECTED_JSON_SHA256 = "34a3f0752816fc7a301e66b63bf036ab881b3f335ebccdfb514883c11d967e1d"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore() -> Path:
    encoded = B64_PATH.read_bytes()
    if sha256(encoded) != EXPECTED_B64_SHA256:
        raise ValueError("legacy semantic base64 seal mismatch")
    compressed = base64.b64decode(encoded)
    if sha256(compressed) != EXPECTED_GZIP_SHA256:
        raise ValueError("legacy semantic gzip seal mismatch")
    raw = gzip.decompress(compressed)
    if sha256(raw) != EXPECTED_JSON_SHA256:
        raise ValueError("legacy semantic JSON seal mismatch")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(raw)
    return OUT_PATH


if __name__ == "__main__":
    print(restore())
