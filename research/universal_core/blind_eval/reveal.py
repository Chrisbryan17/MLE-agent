from __future__ import annotations
from .commitment import verify_commitment
from .contracts import ChallengeCommitment, IndependenceAttestation, PrivateReveal, PublicChallengeSuite, SubmissionEnvelope, timestamp_value
from .errors import ScoringError
from .submission import verify_submission


def validate_independence_attestation(attestation: IndependenceAttestation) -> None:
    if not attestation.source_reviewed:
        raise ScoringError("independence attestation lacks source review")
    if not attestation.generator_source_digests:
        raise ScoringError("independence attestation lacks generator source digests")
    if not attestation.source_material_digests:
        raise ScoringError("independence attestation lacks source material digests")
    if attestation.developers_saw_private_material:
        raise ScoringError("developers saw private material before submission")


def verify_reveal(commitment: ChallengeCommitment, suite: PublicChallengeSuite, submission: SubmissionEnvelope, reveal: PrivateReveal) -> None:
    verify_commitment(commitment,suite,reveal)
    verify_submission(commitment,suite,submission,require_before_reveal=reveal.revealed_at)
    validate_independence_attestation(reveal.independence_attestation)
    if timestamp_value(reveal.independence_attestation.created_at)>timestamp_value(commitment.created_at):
        raise ScoringError("independence attestation was created after commitment")
    expected=[task.task_id for task in suite.tasks]
    actual=[task.task_id for task in reveal.task_reveals]
    if actual!=expected: raise ScoringError("task ordering mismatch")
    for public,private in zip(suite.tasks,reveal.task_reveals):
        if len(private.targets)!=len(public.hidden_inputs): raise ScoringError("reveal target row count mismatch")
    if reveal.scoring_policy.digest!=commitment.scoring_policy_digest: raise ScoringError("scoring policy digest mismatch")
