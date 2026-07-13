#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,pathlib,platform,resource,statistics,time
import bbeh_object_properties_exact_v1 as solver
ROOT=pathlib.Path(os.environ.get('BBEH_TASK_ROOT','.external/bbeh/bbeh/benchmark_tasks'));OUT=pathlib.Path('artifacts/object_properties_exact')
def main():
 path=ROOT/'bbeh_object_properties'/'task.json';examples=json.loads(path.read_text())['examples'];rows=[];times=[]
 for i,e in enumerate(examples):
  t=time.perf_counter()
  try:pred,trace,worlds=solver.solve(e['input'],True);error=None;max_worlds=max([x['worlds'] for x in trace]+[len(worlds)]);final_worlds=len(worlds)
  except Exception as exc:pred=None;trace=[];max_worlds=final_worlds=0;error=f'{type(exc).__name__}: {exc}'
  elapsed=time.perf_counter()-t;times.append(elapsed);rows.append({'index':i,'prediction':pred,'target':e['target'],'correct':pred==e['target'],'latency_seconds':elapsed,'error':error,'max_surviving_worlds':max_worlds,'final_surviving_worlds':final_worlds,'trace':trace})
 correct=sum(r['correct'] for r in rows);OUT.mkdir(parents=True,exist_ok=True)
 payload={'protocol':'Pinned full-task post-development evaluation. Hidden parameters are inferred only from intermediate aggregate checkpoints; unspecified loss branches are all propagated; a numeric answer is emitted only when all final worlds agree.','pinned_bbeh_commit':'80d12ca916b7158f22293fcf3144f4d3d854d4be','environment':{'python':platform.python_version(),'platform':platform.platform()},'aggregate':{'n':len(rows),'correct':correct,'accuracy':correct/len(rows),'coverage':sum(r['prediction'] is not None for r in rows)/len(rows),'median_ms':statistics.median(times)*1000,'p95_ms':sorted(times)[int(.95*(len(times)-1))]*1000,'throughput_per_second':len(rows)/sum(times),'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'max_surviving_worlds':max(r['max_surviving_worlds'] for r in rows),'max_final_worlds':max(r['final_surviving_worlds'] for r in rows)},'task_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'solver_sha256':hashlib.sha256(pathlib.Path(solver.__file__).read_bytes()).hexdigest(),'errors':[r for r in rows if not r['correct']]}
 (OUT/'results.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload['aggregate'],indent=2))
if __name__=='__main__':main()
