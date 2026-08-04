from pathlib import Path


def test_workflow_prefixes_upload_artifact_digest() -> None:
    root = Path(__file__).resolve().parents[4]
    workflow = (root / ".github" / "workflows" / "public-benchmark-snapshot.yml").read_text(encoding="utf-8")
    assert '--artifact-digest "sha256:$ARTIFACT_DIGEST"' in workflow
