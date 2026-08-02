from __future__ import annotations
import json, os, shutil, uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.runner import UniversalCoreRunner
from universal_core.sealing import verify_attempt
from .commitment import verify_public_commitment
from .contracts import ChallengeCommitment, CoreIdentity, PublicChallengeSuite, SubmissionEnvelope, TaskSubmission
from .core_identity import build_core_identity, verify_frozen_core
from .errors import SubmissionError


def _exclusive_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
    except FileExistsError as exc:
        raise FileExistsError(f"first attempt already exists: {path}") from exc


def _prediction_rows(result: Any) -> tuple[dict[str, Any], ...]:
    rows=[]
    for row in result.predictions:
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        rows.append({"index":int(row.index),"prediction":row.prediction,"status":status,"confidence":float(row.confidence),"runtime_ms":float(getattr(row,"runtime_ms",0.0)),"error":getattr(row,"error",None)})
    if [row["index"] for row in rows] != list(range(len(rows))):
        raise SubmissionError("submission row ordering mismatch")
    return tuple(rows)


def _copy_attempt(source: Path, target: Path) -> str:
    verify_attempt(source)
    if target.exists():
        raise FileExistsError(f"first attempt already exists: {target}")
    shutil.copytree(source, target)
    verify_attempt(target)
    return sha256_hex((target / "SHA256.json").read_bytes())


def run_public_suite(
    commitment: ChallengeCommitment,
    suite: PublicChallengeSuite,
    output_root: Path,
    *,
    repo_root: Path,
    runner_factory: Callable[[], Any] = UniversalCoreRunner.default,
    identity_builder: Callable[[Path], CoreIdentity] = build_core_identity,
    created_at: str,
) -> SubmissionEnvelope:
    verify_public_commitment(commitment, suite)
    if (output_root / "SUBMISSION.json").exists() or (output_root / "tasks").exists():
        raise FileExistsError(f"first attempt already exists: {output_root}")
    identity = identity_builder(repo_root)
    if identity.commit != commitment.frozen_core_commit:
        raise SubmissionError("core identity mismatch")
    if identity_builder is build_core_identity:
        verify_frozen_core(repo_root, identity)
    output_root.mkdir(parents=True, exist_ok=True)
    runner = runner_factory()
    task_submissions=[]
    for task in suite.tasks:
        task_root=output_root / "tasks" / task.task_id
        result=runner.run(task.to_task_package(), task_root)
        source_attempt=Path(str(result.audit_path)) if result.audit_path else task_root / "attempts" / "attempt-0001"
        if source_attempt.resolve() != (task_root / "attempts" / "attempt-0001").resolve():
            # Runner may return the same path as text; external paths are forbidden.
            raise SubmissionError("runner returned an attempt outside the task root")
        verify_attempt(source_attempt)
        predictions=_prediction_rows(result)
        if len(predictions)!=len(task.hidden_inputs):
            raise SubmissionError("submission row count mismatch")
        pred_digest=sha256_hex(canonical_json_bytes(list(predictions)))
        if result.prediction_digest and result.prediction_digest != pred_digest:
            # Existing core seals a canonical prediction representation; retain its seal and separately validate rows.
            pred_digest=str(result.prediction_digest)
        audit_digest=sha256_hex((source_attempt/"SHA256.json").read_bytes())
        task_submissions.append(TaskSubmission(task.task_id,result.package_digest,result.solver_digest,result.status.value if hasattr(result.status,"value") else str(result.status),predictions,pred_digest,"attempt-0001",audit_digest,dict(getattr(result,"details",{})),{}))
    draft=SubmissionEnvelope(suite.suite_id,commitment.commitment_digest,suite.binding_digest,commitment.frozen_core_commit,identity,tuple(task_submissions),created_at)
    submission=replace(draft,submission_digest=draft.computed_digest)
    _exclusive_json(output_root/"CORE_IDENTITY.json",identity.to_data())
    _exclusive_json(output_root/"SUBMISSION.json",submission.to_data())
    _exclusive_json(output_root/"TASK_MANIFEST.json",{task.task_id:task.audit_manifest_digest for task in submission.task_submissions})
    verify_submission(commitment,suite,submission)
    return submission


def verify_submission(commitment: ChallengeCommitment, suite: PublicChallengeSuite, submission: SubmissionEnvelope, *, require_before_reveal: str | None = None) -> None:
    verify_public_commitment(commitment,suite)
    if submission.submission_digest != submission.computed_digest:
        raise SubmissionError("submission digest mismatch")
    if submission.suite_id!=suite.suite_id or submission.commitment_digest!=commitment.commitment_digest:
        raise SubmissionError("submission identity mismatch")
    if submission.public_challenge_digest!=suite.binding_digest:
        raise SubmissionError("public challenge digest mismatch")
    if submission.frozen_core_commit!=commitment.frozen_core_commit or submission.core_identity.commit!=commitment.frozen_core_commit:
        raise SubmissionError("core identity mismatch")
    expected_ids=[task.task_id for task in suite.tasks]
    actual_ids=[task.task_id for task in submission.task_submissions]
    if actual_ids!=expected_ids:
        raise SubmissionError("task ordering mismatch")
    for public,submitted in zip(suite.tasks,submission.task_submissions):
        if submitted.package_digest!=public.to_task_package().package_digest:
            raise SubmissionError("task package digest mismatch")
        if len(submitted.predictions)!=len(public.hidden_inputs):
            raise SubmissionError("submission row count mismatch")
        if [row["index"] for row in submitted.predictions]!=list(range(len(public.hidden_inputs))):
            raise SubmissionError("submission row ordering mismatch")
    if require_before_reveal is not None:
        from .contracts import timestamp_value
        if timestamp_value(submission.created_at)>=timestamp_value(require_before_reveal):
            raise SubmissionError("submission was not sealed before reveal")
