#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
B64_PATH = HERE / "DUAL_TRACK_RECOVERY_SOURCE.tar.gz.b64"
PART_GLOB = "DUAL_TRACK_RECOVERY_SOURCE.part*.b64"
MANIFEST_PATH = HERE / "DUAL_TRACK_RECOVERY_SOURCE_MANIFEST.json"


def main() -> None:
    metadata = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if B64_PATH.exists():
        encoded = B64_PATH.read_bytes()
    else:
        parts = sorted(HERE.glob(PART_GLOB))
        if not parts:
            raise FileNotFoundError("no recovery bundle or chunk files found")
        encoded = b"".join(part.read_bytes() for part in parts)
    if hashlib.sha256(encoded).hexdigest() != metadata["base64_file_sha256"]:
        raise ValueError("base64 recovery bundle hash mismatch")
    archive = base64.b64decode(encoded)
    if hashlib.sha256(archive).hexdigest() != metadata["archive_sha256"]:
        raise ValueError("decoded recovery archive hash mismatch")
    repository_root = HERE.parents[3]
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            destination = (repository_root / member.name).resolve()
            if repository_root.resolve() not in destination.parents:
                raise ValueError(f"unsafe archive member: {member.name}")
        bundle.extractall(repository_root, filter="data")
    for relative, expected in metadata["files"].items():
        actual = hashlib.sha256((repository_root / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"restored file hash mismatch: {relative}")
    print(f"restored and verified {len(metadata['files'])} files")


if __name__ == "__main__":
    main()
