#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

import z3

BASE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('BBEH_ROOT','.external/bbeh/bbeh/benchmark_tasks'))
FILES={'core':BASE/'bbeh_exact_robust.py','spatial':BASE/'bbeh_spatial_exact.py','temporal':BASE/'bbeh_temporal_sequence_exact.py','runner':Path(__file__).resolve()}

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def percentile(values,p):
 values=sorted(values);position=(len(values)-1)*p;low=int(position);high=min(len(values)-1,low+1);fraction=position-low
 return values[low]*(1-fraction)+values[high]*fraction

def install_z3_boolean_csp(core):
 def satisfiable(constraints,fixed):
  names=sorted(set(fixed)|{name for constraint in constraints for name in constraint.scope});variables={name:z3.Bool(name) for name in names};solver=z3.Solver()
  for name,value in fixed.items():solver.add(variables[name]==value)
  for constraint in constraints:
   rows=[]
   for allowed in constraint.allowed:rows.append(z3.And([variables[name]==allowed[index] for index,name in enumerate(constraint.scope)]))
   solver.add(z3.Or(rows) if rows else z3.BoolVal(False))
  return solver.check()==z3.sat
 core._csp_satisfiable=satisfiable

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--task',required=True);args=parser.parse_args();task=args.task
 core=load('matrix_core',FILES['core']);install_z3_boolean_csp(core)
 if task=='bbeh_spatial_reasoning':solver=load('matrix_spatial',FILES['spatial']).solve;source='spatial'
 elif task=='bbeh_temporal_sequence':solver=load('matrix_temporal',FILES['temporal']).solve;source='temporal'
 else:solver=core.SOLVERS[task];source='core'
 task_path=ROOT/task/'task.json';examples=json.loads(task_path.read_text())['examples'];rows=[];times=[]
 for index,example in enumerate(examples):
  started=time.perf_counter()
  try:prediction=solver(example['input']);error=None
  except Exception as exc:prediction=None;error=f'{type(exc).__name__}: {exc}'
  elapsed=time.perf_counter()-started;times.append(elapsed);correct=prediction is not None and str(prediction).strip()==str(example['target']).strip()
  rows.append({'index':index,'prediction':prediction,'target':example['target'],'correct':correct,'latency_seconds':elapsed,'error':error})
 result={'task':task,'source':source,'n':len(rows),'correct':sum(row['correct'] for row in rows),'accuracy':sum(row['correct'] for row in rows)/len(rows),'coverage':sum(row['prediction'] is not None for row in rows)/len(rows),'median_ms':statistics.median(times)*1000,'p95_ms':percentile(times,.95)*1000,'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'errors':[row for row in rows if not row['correct']],'environment':{'python':sys.version,'platform':platform.platform()},'task_sha256':hashlib.sha256(task_path.read_bytes()).hexdigest(),'code_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in FILES.items()}}
 output=BASE/'artifacts/exact_matrix';output.mkdir(parents=True,exist_ok=True);(output/f'{task}.json').write_text(json.dumps(result,indent=2,default=str));print(json.dumps({key:result[key] for key in ('task','n','correct','accuracy','coverage')},indent=2))
if __name__=='__main__':main()
