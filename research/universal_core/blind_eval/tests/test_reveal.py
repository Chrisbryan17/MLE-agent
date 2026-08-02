from dataclasses import replace
import pytest
from universal_core.blind_eval.reveal import verify_reveal
from universal_core.blind_eval.submission import run_public_suite
from .conftest import SUBMIT_TIME

def _submission(bundle,tmp_path,identity,factory):
    commitment,public,_=bundle; return run_public_suite(commitment,public,tmp_path,repo_root=tmp_path,runner_factory=factory,identity_builder=lambda _:identity,created_at=SUBMIT_TIME)

def test_reveal_verifies(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal=committed_bundle; submission=_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory); verify_reveal(commitment,public,submission,reveal)

def test_row_count_mismatch_fails(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal=committed_bundle; submission=_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory); bad=replace(reveal.task_reveals[0],targets=(7,)); changed=replace(reveal,task_reveals=(bad,)+reveal.task_reveals[1:]); changed=replace(changed,reveal_digest=changed.computed_digest)
    # Commitment still binds old reveal, so verification must fail before scoring.
    with pytest.raises(Exception): verify_reveal(commitment,public,submission,changed)

def test_reveal_must_follow_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal=committed_bundle; submission=_submission(committed_bundle,tmp_path,fake_identity,fake_runner_factory); changed=replace(reveal,revealed_at="2026-07-30T10:30:00Z"); changed=replace(changed,reveal_digest=changed.computed_digest)
    with pytest.raises(Exception): verify_reveal(commitment,public,submission,changed)
