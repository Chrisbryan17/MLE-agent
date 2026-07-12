#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

import bbeh_exact_robust as exact
import spatial_exact_cell as spatial

DATASET='livebench/reasoning'
BASE='https://datasets-server.huggingface.co'
OUT=Path('artifacts/livebench_eval')
CACHE=Path('.livebench_eval_cache')
PUBLIC_CUTOFF='2024-11-25'
SUPPORTED={'web_of_lies_v2','spatial'}


def get_json(path,params,retries=8):
 url=BASE+path+'?'+urllib.parse.urlencode(params);last=None
 for attempt in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
   with urllib.request.urlopen(req,timeout=180) as r:return json.loads(r.read())
  except Exception as exc:last=exc;time.sleep(min(30,2**attempt))
 raise last

def download(url,path,retries=8):
 if path.exists():return
 path.parent.mkdir(parents=True,exist_ok=True);last=None
 for attempt in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
   with urllib.request.urlopen(req,timeout=300) as r,path.open('wb') as f:
    while True:
     b=r.read(1024*1024)
     if not b:break
     f.write(b)
   return
  except Exception as exc:last=exc;path.unlink(missing_ok=True);time.sleep(min(30,2**attempt))
 raise last

def rows():
 manifest=get_json('/parquet',{'dataset':DATASET});out=[];hashes={}
 for i,entry in enumerate(manifest.get('parquet_files',[])):
  p=CACHE/f'{i:03d}.parquet';download(entry['url'],p);hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
  pf=pq.ParquetFile(p)
  for batch in pf.iter_batches(batch_size=2048):out.extend(batch.to_pylist())
 return out,hashes

def normalized(value):
 if value is None:return None
 return ' '.join(str(value).strip().lower().replace('**','').split())

def solve(row):
 text=row['turns'][0] if isinstance(row.get('turns'),list) else str(row.get('turns',''))
 task=row.get('task')
 if task=='web_of_lies_v2':return exact.solve_web_of_lies(text),'web_of_lies_exact'
 if task=='spatial':return spatial.solve(text),'spatial_exact'
 return None,'abstain_unsupported'

def main():
 OUT.mkdir(parents=True,exist_ok=True);dataset_rows,hashes=rows();records=[]
 for index,row in enumerate(dataset_rows):
  release=str(row.get('livebench_release_date') or row.get('release_date') or '')[:10]
  if release and release>PUBLIC_CUTOFF:continue
  pred,cell=solve(row);gold=row.get('ground_truth');ok=normalized(pred)==normalized(gold)
  records.append({'index':index,'question_id':row.get('question_id'),'task':row.get('task'),'release':release,'cell':cell,'prediction':pred,'target':gold,'correct':ok})
 by_task={}
 for task in sorted({r['task'] for r in records}):
  rr=[r for r in records if r['task']==task];c=sum(r['correct'] for r in rr);cov=sum(r['prediction'] is not None for r in rr)
  by_task[task]={'n':len(rr),'correct':c,'accuracy':c/len(rr),'coverage':cov/len(rr),'errors':[r for r in rr if not r['correct']]}
 n=len(records);correct=sum(r['correct'] for r in records);supported=[r for r in records if r['task'] in SUPPORTED];sc=sum(r['correct'] for r in supported)
 payload={'protocol':'Pinned LiveBench reasoning snapshot. Unsupported tasks abstain and count wrong in full score.','repository_commit':'864b0d7203c66b429d93c43841df0a773f7738c7','public_cutoff':PUBLIC_CUTOFF,'tasks':by_task,'aggregate':{'n':n,'correct':correct,'full_micro_accuracy':correct/n,'full_macro_accuracy':sum(v['accuracy'] for v in by_task.values())/len(by_task),'coverage':sum(r['prediction'] is not None for r in records)/n,'supported_n':len(supported),'supported_correct':sc,'supported_accuracy':sc/len(supported)},'parquet_sha256':hashes,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'results.json').write_text(json.dumps(payload,indent=2,default=str));print(json.dumps(payload['aggregate'],indent=2))
if __name__=='__main__':main()
