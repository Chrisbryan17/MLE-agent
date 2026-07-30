from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


def to_canonical_data(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return to_canonical_data(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_canonical_data(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [to_canonical_data(item) for item in value]
    if isinstance(value, set | frozenset):
        normalized = [to_canonical_data(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    data = to_canonical_data(value)
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
