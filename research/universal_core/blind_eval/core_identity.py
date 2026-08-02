from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Callable
from universal_core.canonical import canonical_json_bytes, sha256_hex
from .constants import FROZEN_CORE_COMMIT
from .contracts import CoreIdentity
from .errors import SubmissionError


def _run(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=repo_root, text=True, capture_output=True, check=False)


def _frozen_paths(repo_root: Path, commit: str) -> tuple[str, ...]:
    result = _run(repo_root, ["git", "ls-tree", "-r", "--name-only", commit, "--", "research/universal_core"])
    if result.returncode:
        raise SubmissionError(f"cannot resolve frozen core tree: {result.stderr.strip()}")
    paths = []
    for path in result.stdout.splitlines():
        if not path.endswith(".py"):
            continue
        relative = path.removeprefix("research/universal_core/")
        if relative.startswith(("tests/", "blind_eval/", "checkpoints/")) or "/__pycache__/" in relative:
            continue
        paths.append(path)
    if not paths:
        raise SubmissionError("frozen core source set is empty")
    return tuple(sorted(paths))


def build_core_identity(repo_root: Path, commit: str = FROZEN_CORE_COMMIT) -> CoreIdentity:
    source_files: dict[str, str] = {}
    for path in _frozen_paths(repo_root, commit):
        result = _run(repo_root, ["git", "show", f"{commit}:{path}"])
        if result.returncode:
            raise SubmissionError(f"cannot read frozen source: {path}")
        source_files[path] = sha256_hex(result.stdout.encode("utf-8"))
    source_digest = sha256_hex(canonical_json_bytes(source_files))
    return CoreIdentity(commit=commit, source_files=source_files, source_digest=source_digest)


def verify_frozen_core(repo_root: Path, identity: CoreIdentity) -> None:
    if identity.commit != FROZEN_CORE_COMMIT:
        raise SubmissionError("core identity commit mismatch")
    expected = build_core_identity(repo_root, identity.commit)
    if expected.to_data() != identity.to_data():
        raise SubmissionError("core identity digest mismatch")
    for path, digest in identity.source_files.items():
        current = repo_root / path
        if not current.is_file():
            raise SubmissionError(f"frozen source file missing: {path}")
        if sha256_hex(current.read_bytes()) != digest:
            raise SubmissionError(f"frozen source file changed: {path}")
