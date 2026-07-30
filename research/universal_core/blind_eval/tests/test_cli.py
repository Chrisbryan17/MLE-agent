import json
from pathlib import Path
from universal_core.blind_eval.cli import main
from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT
from .conftest import COMMIT_TIME,NONCE

def test_commit_cli(public_draft,reveal_draft,tmp_path):
    public=tmp_path/"public.json"; private=tmp_path/"private.json"; public.write_text(json.dumps(public_draft)); private.write_text(json.dumps(reveal_draft)); out=tmp_path/"out"
    assert main(["commit","--public",str(public),"--private",str(private),"--output",str(out),"--created-at",COMMIT_TIME,"--nonce",NONCE])==0
    assert (out/"COMMITMENT.json").is_file() and (out/"PUBLIC_CHALLENGE.json").is_file() and (out/"PRIVATE_REVEAL.json").is_file()

def test_wrong_core_commit_is_protocol_failure(public_draft,reveal_draft,tmp_path):
    public=tmp_path/"public.json"; private=tmp_path/"private.json"; public.write_text(json.dumps(public_draft)); private.write_text(json.dumps(reveal_draft)); out=tmp_path/"committed"; main(["commit","--public",str(public),"--private",str(private),"--output",str(out),"--created-at",COMMIT_TIME,"--nonce",NONCE])
    assert main(["submit","--commitment",str(out/"COMMITMENT.json"),"--challenge",str(out/"PUBLIC_CHALLENGE.json"),"--core-commit","0"*40,"--repo-root",str(tmp_path),"--output",str(tmp_path/"submission"),"--created-at","2026-07-30T11:00:00Z"])==3
