#!/usr/bin/env python3
from __future__ import annotations
import collections,hashlib,json,os,pathlib,platform,resource,statistics,time
import bbeh_buggy_tables_exact_v1 as solver
ROOT=pathlib.Path(os.environ.get('BBEH_TASK_ROOT','.external/bbeh/bbeh/benchmark_tasks'))
OUT=pathlib.Path('artifacts/buggy_tables_exact')

def family(text):
 desc=text.split('However,',1)[1].split('Compute the absolute',1)[0]
 if 'merged every two rows' in desc:return 'merged_rows'
 if 'rotated to the right' in desc:return 'row_rotation'
 if 'rotated down' in desc:return 'column_rotation'
 if 'column-order' in desc:return 'error_replacement_column_order'
 if 'row-order' in desc:return 'error_replacement_row_order'
 if 'failed to save' in desc:return 'omitted_nulls'
 if 'each row' in desc:return 'row_random_tails'
 if 'each column' in desc:return 'column_random_tails'
 return 'unknown'

def main():
 path=ROOT/'bbeh_buggy_tables'/'task.json';examples=json.loads(path.read_text())['examples'];rows=[];times=[]
 for i,e in enumerate(examples):
  t=time.perf_counter()
  try:pred=solver.solve(e['input']);error=None
  except Exception as exc:pred=None;error=f'{type(exc).__name__}: {exc}'
  elapsed=time.perf_counter()-t;times.append(elapsed)
  agg=__import__('re').search(r'between the (mean|median|sum|stdev)',e['input']).group(1)
  rows.append({'index':i,'prediction':pred,'target':e['target'],'correct':pred==e['target'],'family':family(e['input']),'aggregation':agg,'latency_seconds':elapsed,'error':error})
 groups={}
 for key in ('family','aggregation'):
  stats={}
  for name in sorted(set(r[key] for r in rows)):
   subset=[r for r in rows if r[key]==name];c=sum(r['correct'] for r in subset)
   stats[name]={'n':len(subset),'correct':c,'accuracy':c/len(subset)}
  groups[key]=stats
 correct=sum(r['correct'] for r in rows);OUT.mkdir(parents=True,exist_ok=True)
 payload={'protocol':'Pinned full-task post-development evaluation. Every row counts; errors and abstentions count wrong. Reconstruction is completed before query execution.','pinned_bbeh_commit':'80d12ca916b7158f22293fcf3144f4d3d854d4be','environment':{'python':platform.python_version(),'platform':platform.platform()},'aggregate':{'n':len(rows),'correct':correct,'accuracy':correct/len(rows),'coverage':sum(r['prediction'] is not None for r in rows)/len(rows),'median_ms':statistics.median(times)*1000,'p95_ms':sorted(times)[int(.95*(len(times)-1))]*1000,'throughput_per_second':len(rows)/sum(times),'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},'breakdown':groups,'task_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'solver_sha256':hashlib.sha256(pathlib.Path(solver.__file__).read_bytes()).hexdigest(),'errors':[r for r in rows if not r['correct']]}
 (OUT/'results.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload['aggregate'],indent=2));print(json.dumps(groups,indent=2))
if __name__=='__main__':main()
