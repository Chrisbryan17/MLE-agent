from __future__ import annotations
import json, os, shutil, tempfile, zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.sealing import verify_attempt
from .commitment import verify_commitment
from .contracts import ChallengeCommitment, CoreIdentity, PrivateReveal, PublicChallengeSuite, SubmissionEnvelope
from .errors import AuditError
from .scoring import verify_score_report
from .submission import verify_submission


def write_canonical_exclusive(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if path.exists(): raise FileExistsError(f"immutable file already exists: {path}")
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value)); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def _files(root:Path,exclude:set[str])->list[Path]:
    return [path for path in sorted(root.rglob("*")) if path.is_file() and path.relative_to(root).as_posix() not in exclude]


def build_manifest(root:Path,*,exclude=("SHA256SUMS","AUDIT_MANIFEST.json"))->dict[str,str]:
    excluded=set(exclude)
    return {path.relative_to(root).as_posix():sha256_hex(path.read_bytes()) for path in _files(root,excluded)}


def verify_manifest(root:Path,manifest:Mapping[str,str],*,exclude=("SHA256SUMS","AUDIT_MANIFEST.json"))->None:
    actual=build_manifest(root,exclude=exclude)
    expected={str(k):str(v) for k,v in manifest.items()}
    if set(actual)!=set(expected): raise AuditError("manifest file set mismatch")
    mismatches=[path for path in actual if actual[path]!=expected[path]]
    if mismatches: raise AuditError(f"manifest digest mismatch: {mismatches}")


def _sha_lines(root:Path)->str:
    entries=build_manifest(root,exclude=("SHA256SUMS",))
    return "".join(f"{digest}  {path}\n" for path,digest in entries.items())


def _verify_sha_lines(root:Path)->None:
    path=root/"SHA256SUMS"
    if not path.is_file(): raise AuditError("SHA256SUMS missing")
    expected={}
    for line in path.read_text(encoding="utf-8").splitlines():
        try: digest,rel=line.split("  ",1)
        except ValueError as exc: raise AuditError("invalid SHA256SUMS line") from exc
        expected[rel]=digest
    actual=build_manifest(root,exclude=("SHA256SUMS",))
    if expected!=actual: raise AuditError("SHA256SUMS mismatch")


def build_evidence_directory(output_root:Path,commitment:ChallengeCommitment,suite:PublicChallengeSuite,submission_root:Path,reveal:PrivateReveal,report:Mapping[str,Any],environment:Mapping[str,Any])->Path:
    if output_root.exists(): raise FileExistsError(f"evidence directory already exists: {output_root}")
    output_root.mkdir(parents=True)
    submission=SubmissionEnvelope.from_data(json.loads((submission_root/"SUBMISSION.json").read_text()))
    core=CoreIdentity.from_data(json.loads((submission_root/"CORE_IDENTITY.json").read_text()))
    verify_commitment(commitment,suite,reveal); verify_submission(commitment,suite,submission); verify_score_report(report,commitment,suite,submission,reveal)
    write_canonical_exclusive(output_root/"COMMITMENT.json",commitment.to_data())
    write_canonical_exclusive(output_root/"PUBLIC_CHALLENGE.json",suite.to_data())
    write_canonical_exclusive(output_root/"SUBMISSION.json",submission.to_data())
    write_canonical_exclusive(output_root/"PRIVATE_REVEAL.json",reveal.to_data())
    write_canonical_exclusive(output_root/"SCORE_REPORT.json",dict(report))
    write_canonical_exclusive(output_root/"INDEPENDENCE_ATTESTATION.json",reveal.independence_attestation.to_data())
    write_canonical_exclusive(output_root/"ENVIRONMENT.json",dict(environment))
    write_canonical_exclusive(output_root/"CORE_IDENTITY.json",core.to_data())
    attempts=output_root/"attempts"; attempts.mkdir()
    for task in submission.task_submissions:
        source=submission_root/"tasks"/task.task_id/"attempts"/"attempt-0001"
        verify_attempt(source)
        target=attempts/task.task_id/"attempt-0001"
        target.parent.mkdir(parents=True)
        shutil.copytree(source,target); verify_attempt(target)
    manifest=build_manifest(output_root)
    write_canonical_exclusive(output_root/"AUDIT_MANIFEST.json",{"algorithm":"sha256","files":manifest})
    (output_root/"SHA256SUMS").write_text(_sha_lines(output_root),encoding="utf-8",newline="\n")
    _verify_sha_lines(output_root); verify_manifest(output_root,manifest)
    return output_root


def build_deterministic_zip(evidence_root:Path,zip_path:Path)->str:
    if zip_path.exists(): raise FileExistsError(f"immutable archive already exists: {zip_path}")
    zip_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zip_path,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(p for p in evidence_root.rglob("*") if p.is_file()):
            rel=path.relative_to(evidence_root).as_posix()
            info=zipfile.ZipInfo(rel,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.create_system=3; info.external_attr=0o100644<<16; info.extra=b""; info.comment=b""
            archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return sha256_hex(zip_path.read_bytes())


def _safe_extract(zip_path:Path,target:Path)->None:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            pure=PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts: raise AuditError("unsafe ZIP path")
        archive.extractall(target)


def _load(root:Path,name:str)->Any:
    try: return json.loads((root/name).read_text(encoding="utf-8"))
    except Exception as exc: raise AuditError(f"cannot parse {name}") from exc


def _audit_directory(root:Path)->dict[str,Any]:
    _verify_sha_lines(root)
    audit=_load(root,"AUDIT_MANIFEST.json")
    if set(audit)!={"algorithm","files"} or audit["algorithm"]!="sha256": raise AuditError("invalid audit manifest")
    verify_manifest(root,audit["files"])
    commitment=ChallengeCommitment.from_data(_load(root,"COMMITMENT.json")); suite=PublicChallengeSuite.from_data(_load(root,"PUBLIC_CHALLENGE.json")); submission=SubmissionEnvelope.from_data(_load(root,"SUBMISSION.json")); reveal=PrivateReveal.from_data(_load(root,"PRIVATE_REVEAL.json")); report=_load(root,"SCORE_REPORT.json")
    verify_commitment(commitment,suite,reveal); verify_submission(commitment,suite,submission); verify_score_report(report,commitment,suite,submission,reveal)
    nested=0
    for task in submission.task_submissions:
        attempt=root/"attempts"/task.task_id/"attempt-0001"; verify_attempt(attempt); nested+=1
    return {"valid":True,"suite_id":suite.suite_id,"commitment_digest":commitment.commitment_digest,"submission_digest":submission.submission_digest,"report_digest":report["report_digest"],"manifest_entries":len(audit["files"]),"nested_attempt_manifests":nested}


def audit_evidence(path:Path)->dict[str,Any]:
    try:
        if path.is_dir(): return _audit_directory(path)
        if not zipfile.is_zipfile(path): raise AuditError("evidence path is neither a directory nor a ZIP")
        with tempfile.TemporaryDirectory(prefix="blind-eval-audit-") as tmp:
            root=Path(tmp); _safe_extract(path,root); result=_audit_directory(root); result["zip_digest"]=sha256_hex(path.read_bytes()); return result
    except AuditError: raise
    except Exception as exc: raise AuditError(str(exc)) from exc
