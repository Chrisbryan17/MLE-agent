import json
from pathlib import Path
import pytest
from universal_core.blind_eval.evidence import audit_evidence,build_deterministic_zip,build_evidence_directory,build_manifest,verify_manifest,write_canonical_exclusive
from universal_core.blind_eval.scoring import score_submission
from universal_core.blind_eval.submission import run_public_suite
from universal_core.blind_eval.errors import AuditError
from .conftest import SUBMIT_TIME

def _evidence(bundle,tmp_path,identity,factory):
    commitment,public,reveal=bundle; submission_root=tmp_path/"submission"; submission=run_public_suite(commitment,public,submission_root,repo_root=tmp_path,runner_factory=factory,identity_builder=lambda _:identity,created_at=SUBMIT_TIME); report=score_submission(commitment,public,submission,reveal); root=build_evidence_directory(tmp_path/"evidence",commitment,public,submission_root,reveal,report,{"python":"test"}); return root,report

def test_exclusive_write(tmp_path):
    path=tmp_path/"A.json"; write_canonical_exclusive(path,{"a":1})
    with pytest.raises(FileExistsError): write_canonical_exclusive(path,{"a":2})

def test_manifest_detects_extra(tmp_path):
    (tmp_path/"A").write_text("a"); manifest=build_manifest(tmp_path); (tmp_path/"B").write_text("b")
    with pytest.raises(AuditError,match="file set"): verify_manifest(tmp_path,manifest)

def test_evidence_audits_and_zip_is_deterministic(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    root,report=_evidence(committed_bundle,tmp_path,fake_identity,fake_runner_factory); result=audit_evidence(root); assert result["valid"] and result["nested_attempt_manifests"]==2
    first=build_deterministic_zip(root,tmp_path/"a.zip"); second=build_deterministic_zip(root,tmp_path/"b.zip"); assert first==second; assert (tmp_path/"a.zip").read_bytes()==(tmp_path/"b.zip").read_bytes(); assert audit_evidence(tmp_path/"a.zip")["report_digest"]==report["report_digest"]

def test_tampered_evidence_fails(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    root,_=_evidence(committed_bundle,tmp_path,fake_identity,fake_runner_factory); (root/"SCORE_REPORT.json").write_text("{}\n")
    with pytest.raises(AuditError): audit_evidence(root)
