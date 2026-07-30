from pathlib import Path

from universal_core.archive_guard import ARCHIVE_COMMIT, verify_archive


def test_archive_commit_is_the_verified_head() -> None:
    assert ARCHIVE_COMMIT == "a0c099a41c85f267ca6323235a019b2052107873"


def test_archive_guard_reports_deleted_protected_paths(tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        command = " ".join(args)
        if "refs/remotes/origin" in command:
            return type("R", (), {"returncode": 0, "stdout": ARCHIVE_COMMIT + "\n", "stderr": ""})()
        if "rev-parse" in command:
            return type("R", (), {"returncode": 0, "stdout": ARCHIVE_COMMIT + "\n", "stderr": ""})()
        return type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "research/universal_validation/semantic_dual_track_v1.py\n",
                "stderr": "",
            },
        )()

    result = verify_archive(tmp_path, run=fake_run)
    assert result.commit_resolves is True
    assert result.branch_matches is True
    assert result.deleted_protected_paths == (
        "research/universal_validation/semantic_dual_track_v1.py",
    )
