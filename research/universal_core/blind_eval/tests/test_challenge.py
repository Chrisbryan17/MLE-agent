import pytest
from universal_core.blind_eval.challenge import scan_public_payload
from universal_core.blind_eval.errors import ProtocolError

def test_private_metadata_leak_fails():
    with pytest.raises(ProtocolError,match="forbidden public key"): scan_public_payload({"tasks":[{"family_id":"secret"}]})

def test_normal_demo_output_is_allowed(): scan_public_payload({"demonstrations":[{"input":1,"output":2}]})
