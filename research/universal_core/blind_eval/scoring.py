from __future__ import annotations
from copy import deepcopy
from typing import Any, Iterable, Mapping
from universal_core.canonical import canonical_json_bytes, sha256_hex
from .contracts import ChallengeCommitment, GeneralizationLevel, PrivateReveal, PublicChallengeSuite, RowOutcome, SubmissionEnvelope
from .equivalence import answers_equivalent
from .errors import ScoringError
from .reveal import verify_reveal
from .statistics import wilson_interval

_ABSTAIN_STATUSES={"AMBIGUOUS_TASK","INSUFFICIENT_DEMONSTRATIONS","UNSUPPORTED_OPERATION","VERIFICATION_FAILED","LOW_CONFIDENCE"}

def _empty_counts()->dict[str,int]:
    return {"rows":0,"scored_rows":0,"correct":0,"incorrect":0,"attempted":0,"abstained":0,"execution_failures":0,"output_schema_conflicts":0,"evaluator_defect_exclusions":0}

def _finalize(counts:Mapping[str,int])->dict[str,Any]:
    data=dict(counts); scored=data["scored_rows"]; attempted=data["attempted"]
    data["raw_accuracy"]=data["correct"]/scored if scored else 0.0
    data["attempted_accuracy"]=data["correct"]/attempted if attempted else 0.0
    data["coverage"]=attempted/scored if scored else 0.0
    data["abstention_rate"]=data["abstained"]/scored if scored else 0.0
    data["wilson_95"] = list(wilson_interval(data["correct"],scored))
    return data

def _accumulate(target:dict[str,int],outcome:RowOutcome)->None:
    target["rows"]+=1
    if outcome is RowOutcome.EVALUATOR_DEFECT_EXCLUSION:
        target["evaluator_defect_exclusions"]+=1; return
    target["scored_rows"]+=1
    if outcome is RowOutcome.CORRECT: target["correct"]+=1; target["attempted"]+=1
    elif outcome is RowOutcome.INCORRECT: target["incorrect"]+=1; target["attempted"]+=1
    elif outcome is RowOutcome.ABSTAINED: target["abstained"]+=1
    elif outcome is RowOutcome.EXECUTION_FAILURE: target["execution_failures"]+=1
    elif outcome is RowOutcome.OUTPUT_SCHEMA_CONFLICT: target["output_schema_conflicts"]+=1

def _classify(status:str,prediction:Any,target:Any,excluded:bool,rule)->RowOutcome:
    if excluded: return RowOutcome.EVALUATOR_DEFECT_EXCLUSION
    if status=="SOLVED": return RowOutcome.CORRECT if answers_equivalent(prediction,target,rule) else RowOutcome.INCORRECT
    if status in _ABSTAIN_STATUSES: return RowOutcome.ABSTAINED
    if status=="EXECUTION_FAILED": return RowOutcome.EXECUTION_FAILURE
    if status=="OUTPUT_SCHEMA_CONFLICT": return RowOutcome.OUTPUT_SCHEMA_CONFLICT
    return RowOutcome.ABSTAINED

def _digest_report(data:Mapping[str,Any])->str: return sha256_hex(canonical_json_bytes(data))

def score_submission(commitment:ChallengeCommitment,suite:PublicChallengeSuite,submission:SubmissionEnvelope,reveal:PrivateReveal)->dict[str,Any]:
    try: verify_reveal(commitment,suite,submission,reveal)
    except Exception as exc: raise ScoringError(str(exc)) from exc
    overall=_empty_counts(); by_task={}; by_family={}; by_level={str(i):_empty_counts() for i in range(1,5)}; task_accuracies=[]
    reveal_by={x.task_id:x for x in reveal.task_reveals}; submitted_by={x.task_id:x for x in submission.task_submissions}
    for public in suite.tasks:
        private=reveal_by[public.task_id]; submitted=submitted_by[public.task_id]; counts=_empty_counts(); family=by_family.setdefault(private.family_id,_empty_counts()); level=by_level[str(private.generalization_level.value)]
        rule=reveal.scoring_policy.task_rules.get(public.task_id,reveal.scoring_policy.default_rule); exclusions=set(reveal.scoring_policy.exclusions.get(public.task_id,()))
        rows=[]
        for index,(prediction,target) in enumerate(zip(submitted.predictions,private.targets)):
            outcome=_classify(str(prediction["status"]),prediction.get("prediction"),target,index in exclusions,rule)
            for bucket in (counts,family,level,overall): _accumulate(bucket,outcome)
            rows.append({"index":index,"outcome":outcome.value,"status":prediction["status"]})
        finalized=_finalize(counts); finalized["rows_detail"]=rows; by_task[public.task_id]=finalized; task_accuracies.append(finalized["raw_accuracy"])
    finalized_overall=_finalize(overall); finalized_overall["task_macro_average"]=sum(task_accuracies)/len(task_accuracies) if task_accuracies else 0.0
    finalized_levels={key:_finalize(value) for key,value in by_level.items()}; finalized_families={key:_finalize(value) for key,value in sorted(by_family.items())}
    level4=finalized_levels["4"]
    report={"protocol_version":commitment.protocol_version,"suite_id":suite.suite_id,"valid":True,"commitment_digest":commitment.commitment_digest,"public_challenge_digest":suite.binding_digest,"submission_digest":submission.submission_digest,"private_reveal_digest":reveal.reveal_digest,"scoring_policy_digest":reveal.scoring_policy.digest,"first_attempt_id":"attempt-0001","generated_at":reveal.revealed_at,"headline":{"metric":"level_4_first_attempt_raw_accuracy_at_observed_coverage","raw_accuracy":level4["raw_accuracy"],"coverage":level4["coverage"],"correct":level4["correct"],"scored_rows":level4["scored_rows"]},"overall":finalized_overall,"by_level":finalized_levels,"by_family":finalized_families,"by_task":by_task}
    report["report_digest"]=_digest_report(report)
    return report

def verify_score_report(report:Mapping[str,Any],commitment:ChallengeCommitment,suite:PublicChallengeSuite,submission:SubmissionEnvelope,reveal:PrivateReveal)->None:
    observed=dict(report); digest=observed.pop("report_digest",None)
    if digest!=_digest_report(observed): raise ScoringError("score report digest mismatch")
    expected=score_submission(commitment,suite,submission,reveal)
    if canonical_json_bytes(expected)!=canonical_json_bytes(report): raise ScoringError("score report recomputation mismatch")
