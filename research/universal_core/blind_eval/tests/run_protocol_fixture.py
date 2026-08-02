"""Protocol mechanics fixture only; not independent blind-evaluation evidence."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from universal_core.blind_eval.commitment import prepare_committed_bundle
from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT
from universal_core.blind_eval.contracts import ChallengeCommitment,PrivateReveal,PublicChallengeSuite,SubmissionEnvelope
from universal_core.blind_eval.evidence import build_deterministic_zip,build_evidence_directory,write_canonical_exclusive
from universal_core.blind_eval.scoring import score_submission
from universal_core.blind_eval.submission import run_public_suite

FIXED_NONCE="42"*32; COMMIT_TIME="2026-07-30T10:00:00Z"; SUBMIT_TIME="2026-07-30T11:00:00Z"

def run(output:Path,repo_root:Path)->dict:
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    fixtures=Path(__file__).parent/"fixtures"
    public_draft=json.loads((fixtures/"public_challenge_draft.json").read_text())
    reveal_draft=json.loads((fixtures/"private_reveal_draft.json").read_text())
    commitment,public,reveal=prepare_committed_bundle(public_draft,reveal_draft,nonce=FIXED_NONCE,created_at=COMMIT_TIME)
    committed=output/"committed"; committed.mkdir()
    write_canonical_exclusive(committed/"COMMITMENT.json",commitment.to_data()); write_canonical_exclusive(committed/"PUBLIC_CHALLENGE.json",public.to_data()); write_canonical_exclusive(committed/"PRIVATE_REVEAL.json",reveal.to_data())
    submission_root=output/"submission"; submission=run_public_suite(commitment,public,submission_root,repo_root=repo_root,created_at=SUBMIT_TIME)
    report=score_submission(commitment,public,submission,reveal); write_canonical_exclusive(output/"SCORE_REPORT.json",report)
    evidence=build_evidence_directory(output/"evidence",commitment,public,submission_root,reveal,report,{"fixture":"protocol-mechanics","python":"3.12"})
    zip_digest=build_deterministic_zip(evidence,output/"blind-eval-evidence.zip")
    return {"commitment_digest":commitment.commitment_digest,"submission_digest":submission.submission_digest,"report_digest":report["report_digest"],"zip_digest":zip_digest}

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output",required=True); parser.add_argument("--repo-root",default="."); args=parser.parse_args()
    print(json.dumps(run(Path(args.output),Path(args.repo_root)),sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
