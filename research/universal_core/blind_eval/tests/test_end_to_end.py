from universal_core.blind_eval.evidence import audit_evidence,build_deterministic_zip,build_evidence_directory
from universal_core.blind_eval.scoring import score_submission
from universal_core.blind_eval.submission import run_public_suite
from .conftest import SUBMIT_TIME

def test_commit_submit_reveal_score_audit(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal=committed_bundle; sub=tmp_path/"submission"; submission=run_public_suite(commitment,public,sub,repo_root=tmp_path,runner_factory=fake_runner_factory,identity_builder=lambda _:fake_identity,created_at=SUBMIT_TIME); report=score_submission(commitment,public,submission,reveal); root=build_evidence_directory(tmp_path/"evidence",commitment,public,sub,reveal,report,{"runtime":"fixture"}); digest=build_deterministic_zip(root,tmp_path/"evidence.zip"); audited=audit_evidence(tmp_path/"evidence.zip")
    assert audited["valid"]; assert audited["report_digest"]==report["report_digest"]; assert len(digest)==64
