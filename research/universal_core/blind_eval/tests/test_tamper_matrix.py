from dataclasses import replace
import json,pytest
from universal_core.blind_eval.commitment import verify_commitment,verify_public_commitment
from universal_core.blind_eval.evidence import audit_evidence,build_evidence_directory
from universal_core.blind_eval.scoring import score_submission
from universal_core.blind_eval.submission import run_public_suite,verify_submission
from .conftest import SUBMIT_TIME

def test_changed_scoring_policy_fails(committed_bundle):
    commitment,public,reveal=committed_bundle; policy=replace(reveal.scoring_policy,policy_name="changed"); changed=replace(reveal,scoring_policy=policy); changed=replace(changed,reveal_digest=changed.computed_digest)
    with pytest.raises(Exception): verify_commitment(commitment,public,changed)

def test_task_reorder_fails(committed_bundle):
    commitment,public,_=committed_bundle; changed=replace(public,tasks=tuple(reversed(public.tasks)))
    with pytest.raises(Exception): verify_public_commitment(commitment,changed)

def test_unmanifested_file_fails_audit(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal=committed_bundle; subroot=tmp_path/"sub"; submission=run_public_suite(commitment,public,subroot,repo_root=tmp_path,runner_factory=fake_runner_factory,identity_builder=lambda _:fake_identity,created_at=SUBMIT_TIME); report=score_submission(commitment,public,submission,reveal); root=build_evidence_directory(tmp_path/"evidence",commitment,public,subroot,reveal,report,{})
    (root/"EXTRA").write_text("x")
    with pytest.raises(Exception): audit_evidence(root)
