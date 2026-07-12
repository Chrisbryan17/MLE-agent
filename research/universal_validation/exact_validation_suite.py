#!/usr/bin/env python3
from __future__ import annotations
import hashlib,importlib.util,json,os,platform,resource,statistics,sys,time
from pathlib import Path

ROOT=Path(os.environ.get('BBEH_ROOT','.external/bbeh/bbeh/benchmark_tasks'))
BASE=Path(__file__).resolve().parent
MODULES={'core':BASE/'bbeh_exact_robust.py','spatial':BASE/'bbeh_spatial_exact.py','temporal':BASE/'bbeh_temporal_sequence_exact.py'}
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
core=load('validation_core',MODULES['core']);spatial=load('validation_spatial',MODULES['spatial']);temporal=load('validation_temporal',MODULES['temporal'])
SOLVERS=dict(core.SOLVERS);SOLVERS['bbeh_spatial_reasoning']=spatial.solve;SOLVERS['bbeh_temporal_sequence']=temporal.solve

def percentile(xs,p):
 xs=sorted(xs)
 if not xs:return None
 k=(len(xs)-1)*p;lo=int(k);hi=min(len(xs)-1,lo+1);f=k-lo
 return xs[lo]*(1-f)+xs[hi]*f

def main():
 report={'protocol':'Pinned exact-cell evaluation; every prediction timed; failures count wrong.','tasks':{},'environment':{'python':sys.version,'platform':platform.platform()},'code_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in MODULES.items()}}
 all_times=[];total=correct=0
 for task,solver in SOLVERS.items():
  examples=json.loads((ROOT/task/'task.json').read_text())['examples'];rows=[];times=[];start_task=time.perf_counter()
  for i,ex in enumerate(examples):
   t0=time.perf_counter()
   try:pred=solver(ex['input'])
   except Exception as exc:pred=None;err=f'{type(exc).__name__}: {exc}'
   else:err=None
   elapsed=time.perf_counter()-t0;times.append(elapsed);all_times.append(elapsed);ok=str(pred).strip()==str(ex['target']).strip() if pred is not None else False
   rows.append({'index':i,'prediction':pred,'target':ex['target'],'correct':ok,'latency_seconds':elapsed,'error':err})
  c=sum(row['correct'] for row in rows);n=len(rows);correct+=c;total+=n
  report['tasks'][task]={'n':n,'correct':c,'accuracy':c/n,'coverage':sum(row['prediction'] is not None for row in rows)/n,'wall_seconds':time.perf_counter()-start_task,'median_ms':statistics.median(times)*1000,'p95_ms':percentile(times,.95)*1000,'throughput_per_second':n/sum(times),'errors':[row for row in rows if not row['correct']]}
  print(task,c,n,round(c/n,6),flush=True)
 report['aggregate']={'n':total,'correct':correct,'micro_accuracy':correct/total,'implemented_tasks':len(SOLVERS),'median_ms':statistics.median(all_times)*1000,'p95_ms':percentile(all_times,.95)*1000,'throughput_per_second':total/sum(all_times),'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 out=BASE/'artifacts/exact_closeout';out.mkdir(parents=True,exist_ok=True);(out/'results.json').write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report['aggregate'],indent=2))
if __name__=='__main__':main()
