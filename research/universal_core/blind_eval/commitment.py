from __future__ import annotations
import secrets
from dataclasses import replace
from typing import Any, Callable, Mapping
from universal_core.canonical import canonical_json_bytes, sha256_hex
from .challenge import scan_public_payload
from .constants import FROZEN_CORE_COMMIT, MIN_NONCE_BYTES, PROTOCOL_VERSION, ZERO_DIGEST
from .contracts import ChallengeCommitment, PrivateReveal, PublicChallengeSuite
from .errors import CommitmentError, ProtocolError


def generate_nonce(random_bytes: Callable[[int], bytes] = secrets.token_bytes) -> str:
    value = random_bytes(MIN_NONCE_BYTES)
    if not isinstance(value, bytes) or len(value) < MIN_NONCE_BYTES:
        raise ValueError("nonce source returned fewer than 32 bytes")
    return value.hex()


def _digest(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))


def build_commitment(public_suite: PublicChallengeSuite, private_reveal: PrivateReveal, *, created_at: str) -> ChallengeCommitment:
    scan_public_payload(public_suite.binding_data())
    if public_suite.suite_id != private_reveal.suite_id:
        raise CommitmentError("suite identity mismatch")
    if public_suite.frozen_core_commit != FROZEN_CORE_COMMIT:
        raise CommitmentError("frozen core identity mismatch")
    draft = ChallengeCommitment(
        suite_id=public_suite.suite_id,
        public_challenge_digest=public_suite.binding_digest,
        private_reveal_digest=private_reveal.computed_digest,
        scoring_policy_digest=private_reveal.scoring_policy.digest,
        frozen_core_commit=public_suite.frozen_core_commit,
        created_at=created_at,
        commitment_digest=ZERO_DIGEST,
    )
    return replace(draft, commitment_digest=draft.computed_digest)


def verify_public_commitment(commitment: ChallengeCommitment, public_suite: PublicChallengeSuite) -> None:
    scan_public_payload(public_suite.binding_data())
    if commitment.commitment_digest != commitment.computed_digest:
        raise CommitmentError("commitment digest mismatch")
    if public_suite.commitment_digest != commitment.commitment_digest:
        raise CommitmentError("public commitment link mismatch")
    if public_suite.suite_id != commitment.suite_id:
        raise CommitmentError("suite identity mismatch")
    if public_suite.frozen_core_commit != commitment.frozen_core_commit:
        raise CommitmentError("frozen core identity mismatch")
    if public_suite.binding_digest != commitment.public_challenge_digest:
        raise CommitmentError("public challenge digest mismatch")


def verify_commitment(commitment: ChallengeCommitment, public_suite: PublicChallengeSuite, private_reveal: PrivateReveal) -> None:
    verify_public_commitment(commitment, public_suite)
    if private_reveal.commitment_digest != commitment.commitment_digest:
        raise CommitmentError("private commitment link mismatch")
    if private_reveal.suite_id != commitment.suite_id:
        raise CommitmentError("suite identity mismatch")
    if private_reveal.computed_digest != commitment.private_reveal_digest:
        raise CommitmentError("private reveal digest mismatch")
    if private_reveal.reveal_digest != private_reveal.computed_digest:
        raise CommitmentError("private reveal self-digest mismatch")
    if private_reveal.scoring_policy.digest != commitment.scoring_policy_digest:
        raise CommitmentError("scoring policy digest mismatch")


def prepare_committed_bundle(
    public_draft: Mapping[str, Any],
    reveal_draft: Mapping[str, Any],
    *,
    nonce: str | None = None,
    created_at: str,
) -> tuple[ChallengeCommitment, PublicChallengeSuite, PrivateReveal]:
    public_data = dict(public_draft)
    public_data.setdefault("protocol_version", PROTOCOL_VERSION)
    public_data["commitment_digest"] = ZERO_DIGEST
    public_data.setdefault("frozen_core_commit", FROZEN_CORE_COMMIT)
    scan_public_payload({k: v for k, v in public_data.items() if k != "commitment_digest"})
    public = PublicChallengeSuite.from_data(public_data)

    reveal_data = dict(reveal_draft)
    reveal_data.setdefault("protocol_version", PROTOCOL_VERSION)
    reveal_data["commitment_digest"] = ZERO_DIGEST
    reveal_data["reveal_digest"] = ZERO_DIGEST
    reveal_data["nonce"] = nonce or generate_nonce()
    reveal = PrivateReveal.from_data(reveal_data)
    reveal = replace(reveal, reveal_digest=reveal.computed_digest)

    commitment = build_commitment(public, reveal, created_at=created_at)
    public = replace(public, commitment_digest=commitment.commitment_digest)
    reveal = replace(reveal, commitment_digest=commitment.commitment_digest)
    verify_commitment(commitment, public, reveal)
    return commitment, public, reveal
