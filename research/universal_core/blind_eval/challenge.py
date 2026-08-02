from __future__ import annotations
from typing import Any, Mapping
from .constants import FORBIDDEN_PUBLIC_KEYS
from .errors import ProtocolError


def scan_public_payload(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in FORBIDDEN_PUBLIC_KEYS:
                raise ProtocolError(f"forbidden public key at {path}.{key}: {key}")
            scan_public_payload(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            scan_public_payload(item, f"{path}[{index}]")
