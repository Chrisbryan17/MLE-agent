from __future__ import annotations
import argparse, json, platform, sys
from pathlib import Path
from typing import Any, Sequence
from universal_core.canonical import canonical_json_bytes
from .commitment import prepare_committed_bundle
from .contracts import ChallengeCommitment, PrivateReveal, PublicChallengeSuite, SubmissionEnvelope
from .errors import AuditError, ProtocolError
from .evidence import audit_evidence, write_canonical_exclusive
from .scoring import score_submission
from .submission import run_public_suite


def _read(path:str)->Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _write_error(kind:str,message:str)->None:
    sys.stderr.buffer.write(canonical_json_bytes({"error":kind,"message":message}))

def _parser()->argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="universal-core-blind-eval")
    sub=parser.add_subparsers(dest="command",required=True)
    commit=sub.add_parser("commit"); commit.add_argument("--public",required=True); commit.add_argument("--private",required=True); commit.add_argument("--output",required=True); commit.add_argument("--created-at",required=True); commit.add_argument("--nonce")
    submit=sub.add_parser("submit"); submit.add_argument("--commitment",required=True); submit.add_argument("--challenge",required=True); submit.add_argument("--core-commit",required=True); submit.add_argument("--repo-root",required=True); submit.add_argument("--output",required=True); submit.add_argument("--created-at",required=True)
    score=sub.add_parser("score"); score.add_argument("--commitment",required=True); score.add_argument("--challenge",required=True); score.add_argument("--submission",required=True); score.add_argument("--reveal",required=True); score.add_argument("--output",required=True)
    audit=sub.add_parser("audit"); audit.add_argument("--evidence",required=True)
    return parser

def main(argv:Sequence[str]|None=None)->int:
    try:
        args=_parser().parse_args(argv)
        if args.command=="commit":
            commitment,public,reveal=prepare_committed_bundle(_read(args.public),_read(args.private),nonce=args.nonce,created_at=args.created_at)
            root=Path(args.output); root.mkdir(parents=True,exist_ok=True)
            write_canonical_exclusive(root/"COMMITMENT.json",commitment.to_data()); write_canonical_exclusive(root/"PUBLIC_CHALLENGE.json",public.to_data()); write_canonical_exclusive(root/"PRIVATE_REVEAL.json",reveal.to_data())
            sys.stdout.buffer.write(canonical_json_bytes({"commitment_digest":commitment.commitment_digest,"public_challenge_digest":public.binding_digest,"private_reveal_digest":reveal.reveal_digest})); return 0
        if args.command=="submit":
            commitment=ChallengeCommitment.from_data(_read(args.commitment)); public=PublicChallengeSuite.from_data(_read(args.challenge))
            if args.core_commit!=commitment.frozen_core_commit: raise ProtocolError("core identity mismatch")
            submission=run_public_suite(commitment,public,Path(args.output),repo_root=Path(args.repo_root),created_at=args.created_at)
            sys.stdout.buffer.write(canonical_json_bytes({"submission_digest":submission.submission_digest,"tasks":len(submission.task_submissions)})); return 0
        if args.command=="score":
            commitment=ChallengeCommitment.from_data(_read(args.commitment)); public=PublicChallengeSuite.from_data(_read(args.challenge)); submission=SubmissionEnvelope.from_data(_read(args.submission)); reveal=PrivateReveal.from_data(_read(args.reveal)); report=score_submission(commitment,public,submission,reveal)
            output=Path(args.output); output=output if output.suffix==".json" else output/"SCORE_REPORT.json"; write_canonical_exclusive(output,report); sys.stdout.buffer.write(canonical_json_bytes({"report_digest":report["report_digest"],"headline":report["headline"]})); return 0
        if args.command=="audit":
            result=audit_evidence(Path(args.evidence)); sys.stdout.buffer.write(canonical_json_bytes(result)); return 0
        raise RuntimeError("unreachable command")
    except (OSError,json.JSONDecodeError,KeyError,TypeError) as exc:
        _write_error(type(exc).__name__,str(exc)); return 2
    except (ProtocolError,ValueError,FileExistsError) as exc:
        _write_error(type(exc).__name__,str(exc)); return 3

if __name__=="__main__": raise SystemExit(main())
