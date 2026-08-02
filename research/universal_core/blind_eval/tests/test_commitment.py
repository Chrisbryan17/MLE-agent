from dataclasses import replace
import pytest
from universal_core.blind_eval.commitment import generate_nonce,verify_commitment,verify_public_commitment
from universal_core.blind_eval.errors import CommitmentError

def test_nonce_requires_32_bytes():
    assert len(generate_nonce(lambda n:b'x'*n))==64
    with pytest.raises(ValueError): generate_nonce(lambda n:b'x')

def test_committed_bundle_verifies(committed_bundle):
    commitment,public,reveal=committed_bundle; verify_commitment(commitment,public,reveal); assert commitment.commitment_digest==commitment.computed_digest

def test_target_change_breaks_commitment(committed_bundle):
    commitment,public,reveal=committed_bundle; first=replace(reveal.task_reveals[0],targets=(999,11)); changed=replace(reveal,task_reveals=(first,)+reveal.task_reveals[1:])
    with pytest.raises(CommitmentError,match="private reveal digest mismatch"): verify_commitment(commitment,public,changed)

def test_public_change_breaks_commitment(committed_bundle):
    commitment,public,_=committed_bundle; changed=replace(public,public_scoring_specification="changed")
    with pytest.raises(CommitmentError,match="public challenge digest mismatch"): verify_public_commitment(commitment,changed)
