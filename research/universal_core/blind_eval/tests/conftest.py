from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.contracts import AttemptResult, Demonstration, FailureStatus, OutputSchema, PredictionRow
from universal_core.blind_eval.commitment import prepare_committed_bundle
from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT, PROTOCOL_VERSION, ZERO_DIGEST
from universal_core.blind_eval.contracts import CoreIdentity, PublicChallengeSuite, PublicTask

COMMIT_TIME="2026-07-30T10:00:00Z"; SUBMIT_TIME="2026-07-30T11:00:00Z"; REVEAL_TIME="2026-07-30T12:00:00Z"; NONCE="11"*32

@pytest.fixture
def public_task()->PublicTask:
    return PublicTask("task-exact","Return x + 2.",(Demonstration(0,2),Demonstration(1,3),Demonstration(3,5)),(5,9),OutputSchema(kind="number"))

@pytest.fixture
def public_draft(public_task):
    semantic=PublicTask("task-semantic","Return ALERT when text contains red; otherwise CLEAR.",(Demonstration("red sky","ALERT"),Demonstration("blue sky","CLEAR"),Demonstration("red flag","ALERT")),("red apple","green apple"),OutputSchema(kind="enum",enum_values=("ALERT","CLEAR")))
    return {"protocol_version":PROTOCOL_VERSION,"suite_id":"suite-001","frozen_core_commit":FROZEN_CORE_COMMIT,"tasks":[public_task.to_data(),semantic.to_data()],"public_scoring_specification":"Exact first-attempt scoring with mandatory level reports.","metadata":{"sponsor":"external-fixture"}}

@pytest.fixture
def reveal_draft():
    return {"protocol_version":PROTOCOL_VERSION,"suite_id":"suite-001","revealed_at":REVEAL_TIME,"task_reveals":[{"task_id":"task-exact","targets":[7,11],"family_id":"family-arithmetic","generalization_level":1,"construction_method":"manual external fixture","provenance":{"source_digest":"aa"*32},"ambiguity_annotations":{}},{"task_id":"task-semantic","targets":["ALERT","CLEAR"],"family_id":"family-fictional","generalization_level":4,"construction_method":"manual external fixture","provenance":{"source_digest":"bb"*32},"ambiguity_annotations":{}}],"scoring_policy":{"policy_name":"exact-first-attempt","default_rule":{"kind":"EXACT","absolute_tolerance":0.0,"relative_tolerance":0.0,"directed_graph":True},"task_rules":{},"exclusions":{}},"independence_attestation":{"evaluator_id":"evaluator-001","evaluator_key":"test-key","created_at":"2026-07-30T09:00:00Z","source_reviewed":True,"derived_from_repo_tests":False,"developers_saw_private_material":False,"external_model_assistance":None,"generator_source_digests":["cc"*32],"source_material_digests":["dd"*32],"conflicts_of_interest":[],"evaluator_auditor_distinct":True}}

@pytest.fixture
def committed_bundle(public_draft,reveal_draft):
    return prepare_committed_bundle(public_draft,reveal_draft,nonce=NONCE,created_at=COMMIT_TIME)

@pytest.fixture
def fake_identity():
    return CoreIdentity(FROZEN_CORE_COMMIT,{"research/universal_core/canonical.py":"ee"*32},"ff"*32)

class FakeRunner:
    def run(self,package,output_root):
        predictions=[]
        for index,row in enumerate(package.hidden_inputs):
            if isinstance(row,(int,float)): answer=row+2
            else: answer="ALERT" if "red" in row.casefold() else "CLEAR"
            predictions.append(PredictionRow(index,answer,FailureStatus.SOLVED,1.0))
        attempt=output_root/"attempts"/"attempt-0001"; attempt.mkdir(parents=True)
        serial=[{"index":r.index,"prediction":r.prediction,"status":r.status.value,"confidence":r.confidence,"runtime_ms":0.0,"error":None} for r in predictions]
        prediction_bytes=canonical_json_bytes(serial)
        prediction_digest=sha256_hex(prediction_bytes)
        freeze_data={"fixture":"protocol mechanics only","package_digest":package.package_digest}
        manifest_bytes=canonical_json_bytes(freeze_data)
        freeze_digest=sha256_hex(manifest_bytes)
        attempt_bytes=canonical_json_bytes({"attempt_id":"attempt-0001","freeze_digest":freeze_digest,"prediction_digest":prediction_digest,"supersedes_attempt":None})
        contents={"manifest.json":manifest_bytes,"predictions.json":prediction_bytes,"ATTEMPT.json":attempt_bytes}
        for name,content in contents.items(): (attempt/name).write_bytes(content)
        hashes={name:sha256_hex(content) for name,content in sorted(contents.items())}
        (attempt/"SHA256.json").write_bytes(canonical_json_bytes(hashes))
        return AttemptResult(FailureStatus.SOLVED,tuple(predictions),package.package_digest,"ab"*32,prediction_digest,"attempt-0001",str(attempt),{"verified":True})

@pytest.fixture
def fake_runner_factory(): return lambda:FakeRunner()
