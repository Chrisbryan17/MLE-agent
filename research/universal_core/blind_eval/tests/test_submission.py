import json
from dataclasses import replace
from pathlib import Path
import pytest
from universal_core.blind_eval.submission import run_public_suite,verify_submission
from .conftest import SUBMIT_TIME

def test_sealed_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,_=committed_bundle
    submission=run_public_suite(commitment,public,tmp_path,repo_root=tmp_path,runner_factory=fake_runner_factory,identity_builder=lambda _:fake_identity,created_at=SUBMIT_TIME)
    verify_submission(commitment,public,submission); assert submission.submission_digest==submission.computed_digest; assert len(submission.task_submissions)==2
    assert (tmp_path/"SUBMISSION.json").is_file()

def test_first_attempt_cannot_be_overwritten(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,_=committed_bundle; kwargs=dict(repo_root=tmp_path,runner_factory=fake_runner_factory,identity_builder=lambda _:fake_identity,created_at=SUBMIT_TIME)
    run_public_suite(commitment,public,tmp_path,**kwargs)
    with pytest.raises(FileExistsError,match="first attempt"): run_public_suite(commitment,public,tmp_path,**kwargs)

def test_changed_prediction_breaks_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,_=committed_bundle; submission=run_public_suite(commitment,public,tmp_path,repo_root=tmp_path,runner_factory=fake_runner_factory,identity_builder=lambda _:fake_identity,created_at=SUBMIT_TIME)
    first=submission.task_submissions[0]; rows=list(first.predictions); rows[0]=dict(rows[0])|{"prediction":999}; changed=replace(first,predictions=tuple(rows)); envelope=replace(submission,task_submissions=(changed,)+submission.task_submissions[1:])
    with pytest.raises(Exception,match="submission digest mismatch"): verify_submission(commitment,public,envelope)
