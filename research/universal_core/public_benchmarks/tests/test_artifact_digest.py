from research.universal_core.public_benchmarks import snapshot


def test_normalize_artifact_digest_accepts_upload_action_output() -> None:
    raw = "b" * 64
    assert snapshot.normalize_artifact_digest(raw) == f"sha256:{raw}"
    assert snapshot.normalize_artifact_digest(f"sha256:{raw}") == f"sha256:{raw}"
