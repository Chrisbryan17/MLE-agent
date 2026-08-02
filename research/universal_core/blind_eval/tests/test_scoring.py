from dataclasses import replace
import pytest
from universal_core.blind_eval.scoring import score_submission,verify_score_report
from universal_core.blind_eval.submission import run_public_suite
from .conftest import SUBMIT_TIME

def _score(bundle,tmp_path,identity,factory):
    commitment,public,reveal=bundle; submission=run_public_suite(commitment,public,tmp_path,repo_root=tmp_path,runner_factory=factory,identity_builder=lambda _:identity,created_at=SUBMIT_TIME); return commitment,public,reveal,submission,score_submission(commitment,public,submission,reveal)

def test_level_reporting_and_headline(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal,submission,report=_score(committed_bundle,tmp_path,fake_identity,fake_runner_factory)
    assert report["overall"]["correct"]==4; assert report["overall"]["raw_accuracy"]==1.0; assert set(report["by_level"])=={"1","2","3","4"}; assert report["headline"]["metric"]=="level_4_first_attempt_raw_accuracy_at_observed_coverage"; assert report["headline"]["raw_accuracy"]==1.0; verify_score_report(report,commitment,public,submission,reveal)

def test_report_mutation_fails(committed_bundle,tmp_path,fake_identity,fake_runner_factory):
    commitment,public,reveal,submission,report=_score(committed_bundle,tmp_path,fake_identity,fake_runner_factory); report=dict(report); report["headline"]=dict(report["headline"])|{"raw_accuracy":0.0}
    with pytest.raises(Exception,match="digest mismatch"): verify_score_report(report,commitment,public,submission,reveal)
