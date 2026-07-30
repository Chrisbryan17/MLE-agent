from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

ARCHIVE_BRANCH = "archive/universal-bbeh-dual-track-4520-2026-07-28"
ARCHIVE_COMMIT = "a0c099a41c85f267ca6323235a019b2052107873"
PROTECTED_PREFIXES = (
    "research/universal_validation/",
    ".github/workflows/universal-semantic-dual-track-v1.yml",
)


@dataclass(frozen=True)
class ArchiveVerification:
    commit_resolves: bool
    branch_matches: bool
    deleted_protected_paths: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.commit_resolves and self.branch_matches and not self.deleted_protected_paths


def _invoke(
    run: Callable[..., object],
    args: Sequence[str],
    repo_root: Path,
) -> object:
    return run(
        list(args),
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def verify_archive(
    repo_root: Path,
    run: Callable[..., object] = subprocess.run,
) -> ArchiveVerification:
    resolve = _invoke(run, ("git", "rev-parse", ARCHIVE_COMMIT), repo_root)
    branch = _invoke(
        run,
        ("git", "rev-parse", f"refs/remotes/origin/{ARCHIVE_BRANCH}"),
        repo_root,
    )
    deleted = _invoke(
        run,
        (
            "git",
            "diff",
            "--name-only",
            "--diff-filter=D",
            f"{ARCHIVE_COMMIT}...HEAD",
            "--",
            *PROTECTED_PREFIXES,
        ),
        repo_root,
    )
    return ArchiveVerification(
        commit_resolves=resolve.returncode == 0 and resolve.stdout.strip() == ARCHIVE_COMMIT,
        branch_matches=branch.returncode == 0 and branch.stdout.strip() == ARCHIVE_COMMIT,
        deleted_protected_paths=tuple(line for line in deleted.stdout.splitlines() if line),
    )


def main() -> None:
    result = verify_archive(Path.cwd())
    print(json.dumps({**asdict(result), "ok": result.ok}, indent=2, sort_keys=True))
    if not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
