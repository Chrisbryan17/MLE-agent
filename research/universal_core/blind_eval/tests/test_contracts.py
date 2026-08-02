import math, pytest
from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT,PROTOCOL_VERSION,ZERO_DIGEST
from universal_core.blind_eval.contracts import EquivalenceRule,GeneralizationLevel,PrivateReveal,PublicChallengeSuite,PublicTask

def test_protocol_identity_is_pinned():
    assert PROTOCOL_VERSION=="universal-core-blind-eval-v1"; assert FROZEN_CORE_COMMIT=="89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9"; assert [x.value for x in GeneralizationLevel]==[1,2,3,4]

def test_public_binding_excludes_commitment(public_draft):
    data=dict(public_draft); data["commitment_digest"]=ZERO_DIGEST; suite=PublicChallengeSuite.from_data(data)
    assert "commitment_digest" not in suite.binding_data(); assert suite.to_data()["commitment_digest"]==ZERO_DIGEST

def test_private_binding_excludes_links(committed_bundle):
    _,_,reveal=committed_bundle; assert "commitment_digest" not in reveal.binding_data(); assert "reveal_digest" not in reveal.binding_data()

def test_unknown_fields_fail(public_task):
    with pytest.raises(ValueError,match="unknown PublicTask fields"): PublicTask.from_data(public_task.to_data()|{"family_id":"secret"})

def test_nonfinite_and_bad_tolerance_fail(public_task):
    data=public_task.to_data(); data["hidden_inputs"]=[math.inf]
    with pytest.raises(ValueError,match="non-finite"): PublicTask.from_data(data)
    with pytest.raises(ValueError,match="nonnegative"): EquivalenceRule(absolute_tolerance=-1)
